#!/usr/bin/env python3
"""
Stream Operator Extractor for C++ Code

This script uses tree-sitter to parse C++ code and extract all usages of the << operator,
converting them to string patterns according to specific rules:
- string_literal -> append the literal content
- call_expression -> append "%s"
- identifier -> append "%s"
- qualified_identifier -> append "%s"
- other types -> fail with detailed error

Usage:
    python3 extract_strings_from_cplusplus.py input.cpp [output.json]
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    import tree_sitter_cpp as tscpp
    from tree_sitter import Language, Parser, Node
    TREESITTER_AVAILABLE = True
except ImportError:
    TREESITTER_AVAILABLE = False
    print("Error: tree-sitter dependencies not found.")
    print("Install with: pip install tree-sitter tree-sitter-cpp")
    sys.exit(1)

try:
    from pybloom_live import BloomFilter
    PYBLOOM_AVAILABLE = True
except ImportError:
    try:
        from pybloom import BloomFilter
        PYBLOOM_AVAILABLE = True
    except ImportError:
        PYBLOOM_AVAILABLE = False
        print("Warning: pybloom not found. Bloom filter functionality will be disabled.")
        print("Install with: pip install pybloom-live or pip install pybloom")
        sys.exit(1)


class StreamOperatorExtractor:
    """Extract << operator patterns from C++ code using tree-sitter."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.language = Language(tscpp.language())
        self.parser = Parser(self.language)
        self.extracted_patterns = []
        self.stringbuilder_patterns = []
        self.stringbuilder_identifiers = {}
        self.comments = set()
        self.string_literals = set()
        self.errors = []
        
        # Initialize bloom filter for tracking visited string_literal nodes
        self.string_literal_bloom = BloomFilter(capacity=100000, error_rate=0.001)
        
    def _get_node_text(self, node: Node, source_code: str) -> str:
        """Get the text content of a node."""
        return source_code[node.start_byte:node.end_byte]
    
    def _check_min_length(self, string: str) -> bool:
        """Check if the string meets the minimum word requirement."""
        min_words = 3        
        return len(string.split())>= min_words

    def _mark_string_literal_as_processed(self, node: Node, source_code: str) -> None:
        """Check if a string literal has already been visited and handle duplicates.
        """
        node_text = self._get_node_text(node, source_code)
        string_literal_key = f"{node.start_byte}_{node.end_byte}_{node_text}"
        
        if string_literal_key in self.string_literal_bloom:
            # We dont expect the string_literal to have been already visited as part of _process_right_operand
            print(f"\033[91mERROR: Already visited string literal - this indicates a parsing issue!\033[0m")
            print(f"\033[91mNode details:\033[0m")
            print(f"  Text: '{node_text}'")
            print(f"  Position: line {node.start_point[0] + 1}, column {node.start_point[1] + 1}")
            print(f"  Byte range: {node.start_byte}-{node.end_byte}")
            print(f"  Node type: {node.type}")
            print(f"  Key: {string_literal_key}")
            print(f"\033[91mDebugging tips:\033[0m")
            print(f"  1. Check the source file at line {node.start_point[0] + 1}")
            print(f"  2. Look for duplicate processing in the AST traversal")
            print(f"  3. Verify tree-sitter parsing logic")               
            
            # Exit with error code to indicate parsing issue
            sys.exit(1)
        
        # Add to bloom filter to track visited nodes
        self.string_literal_bloom.add(string_literal_key)
        return False

    def _normalize_string_for_output(self, input_string: str) -> str:
        """Normalize the extracted string for output."""
        
        # Extract string content (remove quotes)
        content = input_string.strip('"')
        if self.verbose:
            print(f"    String literal: '{content}'")
        return content

    def _raise_error_at_node(self, node: Node, source_code: str) -> None:
        """Raise an error at the specified node."""
        node_text = self._get_node_text(node, source_code)
        error_msg = (
            f"Unsupported node type in << operator: '{node.type}'\n"
            f"  Node text: {node_text}\n"
            f"  Node type: {node.type}\n"
            f"  Node position: line {node.start_point[0] + 1}, column {node.start_point[1] + 1}"            
        )
        self.errors.append(error_msg)
        raise ValueError(error_msg)

    def _process_binary_expression(self, node: Node, source_code: str) -> Optional[tuple]:
        """Process a binary expression to extract << operator patterns."""
        if node.type != 'binary_expression':
            return None
            
        # Check if this is a << operator
        operator_node = None
        left_node = None
        right_node = None
        
        # Binary expressions in tree-sitter typically have 3 children: left, operator, right
        if len(node.children) == 3:
            left_node = node.children[0]
            operator_node = node.children[1]
            right_node = node.children[2]
        elif len(node.children) > 3:
            # Handle cases with more than 3 children
            left_node = node.children[0]
            operator_node = node.children[1]
            
            #Exclude nodes that we dont care about
            for child in node.children[2:]:
                if right_node is not None:
                    self._raise_error_at_node(node, source_code)

                if child.type == 'comment':
                    continue
                else:
                    right_node = child                    
        else:
            if self.verbose:
                print(f"  Skipping binary_expression with {len(node.children)} children")
            return None
        
        # Check if the operator is <<
        operator_text = self._get_node_text(operator_node, source_code).strip()
        if operator_text != '<<':
            return None
        
        if self.verbose:
            left_text = self._get_node_text(left_node, source_code)
            right_text = self._get_node_text(right_node, source_code)
            print(f"  Found << operator: {left_text} << {right_text}")
            print(f"    Left type: {left_node.type}")
            print(f"    Right type: {right_node.type}")
        
        # Process the right operand according to rules
        right_operand_value = self._process_right_operand(right_node, source_code)

        if (right_operand_value is None):
            if self.verbose:
                print(f"  Skipping << operator due to unsupported right operand: {self._get_node_text(right_node, source_code)} with type: {right_node.type}")
            return None

        # Check if this is a StringBuilder operation
        IsStringBuilderOperation = False
        identifier_text = None
        if left_node.type == 'call_expression':
            expression_text = self._get_node_text(left_node, source_code)
            if expression_text in ['str::stream()', 'std::stream()']:
                IsStringBuilderOperation = True
                if self.verbose:
                    print(f"\033[92m  Found {expression_text} call expression on left - StringBuilder operation detected\033[0m")
        elif left_node.type == 'qualified_identifier':
            qualified_identifier_text = self._get_node_text(left_node, source_code)
            if qualified_identifier_text in ['std::cout', 'std::cerr', 'std::clog']:
                IsStringBuilderOperation = True
                if self.verbose:
                    print(f"\033[92m  Found {qualified_identifier_text} qualified identifier on left - StringBuilder operation detected\033[0m")
        elif left_node.type == 'identifier':
            # We are assigning the output to a variable of StringBuilder type
            identifier_text = self._get_node_text(left_node, source_code)            
            IsStringBuilderOperation = True

        return (IsStringBuilderOperation, identifier_text, right_operand_value)

    def _process_concatenated_string(self, node: Node, source_code: str) -> str:
        """Process a concatenated string according to the specified rules."""
        concatenated_str = ""

        # Process all child nodes for string
        for child in node.children:
            child_text = self._get_node_text(child, source_code)
            if child.type == 'string_literal':      
                concatenated_str += self._normalize_string_for_output(child_text) 
                self._mark_string_literal_as_processed(child, source_code)
            elif child.type in ['ERROR', 'identifier']:
                # We only extract string literals but they can be hidden behind macros that tree-sitter is not aware of
                # Replace those macros with %s
                concatenated_str += "%s"
            elif child.type == 'comment':
                # Ignore comments
                continue
            else:
                error_msg = (
                    f"Unsupported node type in _process_concatenated_string: '{child.type}'\n"
                    f"  Node text: {child_text}\n"
                    f"  Node position: line {child.start_point[0] + 1}, column {child.start_point[1] + 1}\n"
                    f"  Expected types: string_literal\n"
                    f"  Found type: {child.type}"
                )
                self.errors.append(error_msg)
                raise ValueError(error_msg)

        if self.verbose:
            print(f"    Concatenated string: {concatenated_str}")
        return concatenated_str

    def _process_user_defined_literal(self, node: Node, source_code: str) -> str:
        """Process a user-defined literal according to the specified rules."""
        user_defined_str = ""

        # Process all child nodes for string
        for child in node.children:
            child_text = self._get_node_text(child, source_code)
            if child.type == 'string_literal':
                user_defined_str += self._normalize_string_for_output(child_text) 
                self._mark_string_literal_as_processed(child, source_code)
            elif child.type == 'literal_suffix':
                # Ignore suffixes
                continue
            else:
                error_msg = (
                    f"Unsupported node type in _process_user_defined_literal: '{child.type}'\n"
                    f"  Node text: {child_text}\n"
                    f"  Node position: line {child.start_point[0] + 1}, column {child.start_point[1] + 1}\n"
                    f"  Expected types: string_literal\n"
                    f"  Found type: {child.type}"
                )
                self.errors.append(error_msg)
                raise ValueError(error_msg)

        if self.verbose:
            print(f"    User-defined string: {user_defined_str}")
        return user_defined_str

    def _process_right_operand(self, node: Node, source_code: str) -> str:
        """Process the right operand of << according to the specified rules."""
        node_type = node.type
        node_text = self._get_node_text(node, source_code)
        
        if node_type == 'binary_expression':
            if self.verbose:
                print(f"    Binary expression: {node_text} -> %s")
            return "%s"

        elif node_type == 'call_expression':
            if self.verbose:
                print(f"    Call expression: {node_text} -> %s")
            return "%s"
        
        elif node_type == 'char_literal':
            if self.verbose:
                print(f"    Char literal: {node_text}")
            return node_text.strip('\'')

        elif node_type == 'concatenated_string':
            concatenated_str = self._process_concatenated_string(node, source_code)
            if self.verbose:
                print(f"    Concatenated string: {node_text} -> {concatenated_str}")
            return concatenated_str
        
        elif node_type == 'false':
            return '0'
        
        elif node_type == 'field_expression':
            if self.verbose:
                print(f"    Field expression: {node_text} -> %s")
            return "%s"
            
        elif node_type == 'identifier':
            if self.verbose:
                print(f"    Identifier: {node_text} -> %s")

            if node_text in ['endl']:
                # Special case for string end.  Return empty string
                return ""
            else:
                return "%s"

        elif node_type == 'number_literal':
            # Ignore numbers or boolean following <<
            return "%d"
        
        elif node_type == 'parenthesized_expression':
            # TODO: Handle for string literals inside the expression
            if self.verbose:
                print(f"    Parenthesized expression: {node_text} -> %s")
            return "%s"
        
        elif node_type == 'pointer_expression':
            if self.verbose:
                print(f"    Pointer expression: {node_text} -> %s")
            return "%s"

        elif node_type == 'qualified_identifier':
            # Handle namespaced identifiers like std::cout, ViewGraph::kMaxViewDepth, std::endl
            if self.verbose:
                print(f"    Qualified identifier: {node_text} -> %s")
            
            if node_text in ['std::endl']:
                # Special case for string end.  Return empty string
                return ""
            else:
                return "%s"
        
        elif node_type == 'string_literal':
            # Check if we've already processed this string literal
            self._mark_string_literal_as_processed(node, source_code)

            # Extract string content (remove quotes)
            return self._normalize_string_for_output(node_text)
        
        elif node_type == 'subscript_expression':
            if self.verbose:
                print(f"    Subscript expression: {node_text} -> %s")
            return "%s"
        
        elif node_type == 'true':
            return '1'
        
        elif node_type == 'user_defined_literal':
            user_defined_str = self._process_user_defined_literal(node, source_code)
            if self.verbose:
                print(f"    User-defined string: {node_text} -> {user_defined_str}")
            return user_defined_str

        else:
            # Unsupported node type - fail with detailed error
            error_msg = (
                f"Unsupported node type in << operator: '{node_type}'\n"
                f"  Node text: {node_text}\n"
                f"  Node position: line {node.start_point[0] + 1}, column {node.start_point[1] + 1}\n"
                f"  Expected types: string_literal, call_expression, identifier, qualified_identifier\n"
                f"  Found type: {node_type}"
            )
            self.errors.append(error_msg)
            raise ValueError(error_msg)
    
    def _process_init_declarator(self, node: Node, source_code: str) -> None:
        """Process init_declarator nodes to find StringBuilder variable declarations."""
        if node.type != 'init_declarator':
            return

        variable_name = ""
        is_equality = False
        # Look for StringBuilder() constructor calls in the initializer
        for child in node.children:
            if child.type == 'identifier':
                # Find the variable name (identifier)
                variable_name = self._get_node_text(child, source_code)
            elif child.type == '=':
                is_equality = True
            elif child.type in ['call_expression', 'parenthesized_expression']:
                # Check if this is being initialized with StringBuilder()
                expr_text = self._get_node_text(child, source_code)
                if 'StringBuilder' in expr_text:
                    if is_equality:
                        # Store the StringBuilder variable with empty string value
                        self.stringbuilder_identifiers[variable_name] = ""
                        if self.verbose:
                            print(f"\033[94m  Found StringBuilder declaration: {variable_name}\033[0m")
                        break
                    else:
                        if self.verbose:
                            print(f"\033[94m  Found StringBuilder declaration: {variable_name} but is_equality is false\033[0m")
                        break

    def _process_declaration(self, node: Node, source_code: str) -> None:
        """Process declaration nodes to find StringBuilder variable declarations."""
        if node.type != 'declaration':
            return

        variable_name = ""
        is_stringbuilder = False
        # Look for StringBuilder() constructor calls in the initializer
        for child in node.children:
            if child.type == 'identifier':
                # Find the variable name (identifier)
                variable_name = self._get_node_text(child, source_code)
            elif child.type == 'type_identifier':
                # Check if this is being initialized with StringBuilder()
                expr_text = self._get_node_text(child, source_code)
                if 'StringBuilder' in expr_text:
                    is_stringbuilder = True
        
        # If we found a StringBuilder, add to the identifiers dictionary
        if is_stringbuilder and variable_name:
            self.stringbuilder_identifiers[variable_name] = ""
            if self.verbose:
                print(f"\033[94m  Found StringBuilder declaration: {variable_name}\033[0m")

    def _process_comment(self, node: Node, source_code: str) -> None:
        """Process comment nodes to extract strings."""
        if node.type != 'comment':
            return

        # Skip the comment at the start of the file
        if node.start_byte == 0:
            return
        
        comment_text = self._get_node_text(node, source_code)
        if comment_text.startswith("/*"):
            # Remove /* and */
            comment_text = comment_text[2:-2]
            # Remove leading '*' and whitespace from each line
            lines = [re.sub(r'^\s*\* ?', '', line) for line in comment_text.splitlines()]
            comment_text = " ".join(line.strip() for line in lines if line.strip())
        elif comment_text.startswith("//"):
            comment_text = comment_text[2:].strip()
        comment_text = comment_text.strip()

        # Ignore comments with less than 3 words
        if not self._check_min_length(comment_text):
            return
            
        self.comments.add(comment_text)

    def _process_string_literal(self, node: Node, source_code: str) -> None:
        """Process string literal nodes to extract their values."""
        if node.type != 'string_literal':
            return

        # Check if the node_text matches min_length requirements
        node_text = self._get_node_text(node, source_code)
        if not self._check_min_length(node_text):
                return

        # Check if we have already processed this string_literal as part of other flows
        # e.g. << processing
        string_literal_key = f"{node.start_byte}_{node.end_byte}_{node_text}"        
        if string_literal_key not in self.string_literal_bloom:
            norm_str = self._normalize_string_for_output(node_text)
            self.string_literals.add(norm_str)
            self.string_literal_bloom.add(string_literal_key)
   
    def _extract_from_node(self, node: Node, source_code: str, path: str = "") -> tuple:
        """Recursively extract << patterns from a node and its children."""
        current_path = f"{path}/{node.type}" if path else node.type
        extracted_pattern = ""
        identifier_text = None
        has_stringbuilder_operation = False
        
        # Process this node if it's a binary expression
        if node.type == 'binary_expression':
            try:
                result = self._process_binary_expression(node, source_code)
                if result is not None:
                    has_stringbuilder_operation, identifier_text, extracted_pattern = result
                    self.extracted_patterns.append({
                        'pattern': extracted_pattern,
                        'identifier': identifier_text,
                        'IsStringBuilderOperation': has_stringbuilder_operation
                    })
            except ValueError as e:
                if self.verbose:
                    print(f"Error processing binary expression at {current_path}: {e}")
                # Re-raise to stop processing
                raise
        
        # Process init_declarator nodes to find StringBuilder declarations
        elif node.type == 'init_declarator':
            self._process_init_declarator(node, source_code)

        # Process declaration nodes to find StringBuilder declarations
        elif node.type == 'declaration':
            self._process_declaration(node, source_code)

        # Process comment nodes to extract strings
        elif node.type == 'comment':
            self._process_comment(node, source_code)

        # Process concatenated_string to combine multiple string literals into a single string
        elif node.type == 'concatenated_string':
            concatenated_str = self._process_concatenated_string(node, source_code)

            if not self._check_min_length(concatenated_str):
                return

            self.string_literals.add(concatenated_str)

        # Finally, extract all string literals if they have not been processed already
        elif node.type == 'string_literal':
            self._process_string_literal(node, source_code)

        # Recursively process children
        for child in node.children:
            child_has_sb, child_identifier, child_pattern = self._extract_from_node(child, source_code, current_path)
            if child_has_sb:
                extracted_pattern = child_pattern + extracted_pattern
                identifier_text = child_identifier
                has_stringbuilder_operation = True

        # If the current node is not binary_expression but has_stringbuilder_operation is true,
        # it means that its child nodes returned it a string builder pattern which it should capture.
        if node.type != 'binary_expression' and has_stringbuilder_operation:
            if identifier_text is not None:
                # Recursively extract the identifier from the children
                existing_identifier_value = self.stringbuilder_identifiers.get(identifier_text, None)
                if existing_identifier_value is None:
                    if self.verbose:                        
                        # We dont expect to end here with no existing_identifier_value
                        print(f"\033[91mERROR: existing_identifier_value cannot be None - this indicates a parsing issue!\033[0m")
                        print(f"\033[91mNode details:\033[0m")
                        print(f"  Text: '{self._get_node_text(node, source_code)}'")
                        print(f"  Current Path: {current_path}")
                        print(f"  Position: line {node.start_point[0] + 1}, column {node.start_point[1] + 1}")
                        print(f"  Byte range: {node.start_byte}-{node.end_byte}")
                        print(f"  Node type: {node.type}")
                    else:
                        existing_identifier_value = ""                    
                self.stringbuilder_identifiers[identifier_text] = existing_identifier_value + extracted_pattern
            else:
                if not self._check_min_length(extracted_pattern):
                    if self.verbose:
                        print(f"Skipping short extracted pattern: '{extracted_pattern}'")
                else:
                    self.stringbuilder_patterns.append({
                        'pattern': extracted_pattern,
                        'IsStringBuilderOperation': has_stringbuilder_operation
                    })

            has_stringbuilder_operation = False
            extracted_pattern = ""

        return (has_stringbuilder_operation, identifier_text, extracted_pattern)

    def extract_from_file(self, file_path: str) -> List[str]:
        """Extract all << operator patterns from a C++ file."""
        if not Path(file_path).exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Read source code
        with open(file_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        if self.verbose:
            print(f"Parsing file: {file_path}")
        
        # Parse with tree-sitter
        tree = self.parser.parse(bytes(source_code, 'utf-8'))
        root_node = tree.root_node
        
        # Reset state
        self.extracted_patterns = []
        self.stringbuilder_patterns = []
        self.stringbuilder_identifiers = {}
        self.comments = set()
        self.string_literals = set()
        self.errors = []
        
        # Extract patterns
        try:
            has_stringbuilder, concatenated_result = self._extract_from_node(root_node, source_code)
            if self.verbose and has_stringbuilder:
                print(f"\n\033[92m[DEBUG] Concatenated StringBuilder result: '{concatenated_result}'\033[0m")
        except ValueError:
            # Error details already stored in self.errors
            pass
        
        if self.verbose:
            print(f"Extracted {len(self.extracted_patterns)} patterns")
            print(f"Extracted {len(self.stringbuilder_patterns)} stringbuilder patterns")
            if self.errors:
                print(f"Encountered {len(self.errors)} errors")
        
        return self.extracted_patterns.copy()
    
    def get_errors(self) -> List[str]:
        """Get any errors encountered during extraction."""
        return self.errors.copy()
    
    def get_stringbuilder_patterns(self) -> List[str]:
        """Get any StringBuilder patterns encountered during extraction."""
        return self.stringbuilder_patterns.copy()
    
    def get_stringbuilder_identifiers(self) -> Dict[str, str]:
        """Get any StringBuilder identifiers encountered during extraction."""
        return self.stringbuilder_identifiers.copy()
    
    def get_comments(self) -> List[str]:
        """Get any comments encountered during extraction."""
        return self.comments.copy()
    
    def get_string_literals(self) -> List[str]:
        """Get any string literals encountered during extraction."""
        return self.string_literals.copy()


def main():
    """Command line interface for the
      stream operator extractor."""
    parser = argparse.ArgumentParser(
        description='Extract << operator patterns from C++ code',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s file.cpp                    # Print patterns to stdout
  %(prog)s file.cpp output.json        # Save patterns to JSON file
  %(prog)s file.cpp -v                 # Verbose output with details
        """
    )
    
    parser.add_argument('input_file', help='Input C++ file to parse')
    parser.add_argument('output_file', nargs='?', help='Output JSON file (optional)')
    parser.add_argument('-v', '--verbose', action='store_true', 
                       help='Enable verbose output')
    parser.add_argument('--pretty', action='store_true',
                       help='Pretty-print JSON output')
    
    args = parser.parse_args()
    
    # Validate input file
    if not Path(args.input_file).exists():
        print(f"Error: Input file '{args.input_file}' not found", file=sys.stderr)
        sys.exit(1)
    
    # Check file extension
    input_path = Path(args.input_file)
    if input_path.suffix.lower() not in ['.cpp', '.cc', '.cxx', '.c', '.hpp', '.h']:
        print(f"Warning: '{args.input_file}' may not be a C++ file", file=sys.stderr)
    
    try:
        # Create extractor
        extractor = StreamOperatorExtractor(verbose=args.verbose)
        
        # Extract patterns
        patterns = extractor.extract_from_file(args.input_file)
        errors = extractor.get_errors()
        stringbuilder_patterns = extractor.get_stringbuilder_patterns()
        stringbuilder_identifiers = extractor.get_stringbuilder_identifiers()
        comments = extractor.get_comments()
        string_literals = extractor.get_string_literals()

        # Handle errors
        if errors:
            print(f"Extraction failed with {len(errors)} error(s):", file=sys.stderr)
            for i, error in enumerate(errors, 1):
                print(f"\nError {i}:", file=sys.stderr)
                print(error, file=sys.stderr)
            sys.exit(1)
        
        # Prepare output data
        output_data = {
            "file": str(input_path),
            "patterns": patterns,
            "stringbuilder_patterns": stringbuilder_patterns,
            "stringbuilder_identifiers": stringbuilder_identifiers,
            "comments": comments,
            "string_literals": string_literals
        }

        # Combine all strings into a single array
        combined_strings = []
        # Add stringbuilder patterns
        for sb_pattern in stringbuilder_patterns:
            if isinstance(sb_pattern, dict):
                combined_strings.append(sb_pattern.get('pattern', ''))
            else:
                combined_strings.append(str(sb_pattern))
        # Add stringbuilder identifier values
        combined_strings.extend(stringbuilder_identifiers.values())
        # Add comments
        combined_strings.extend(comments)
        # Add string literals
        combined_strings.extend(string_literals)

        # Output results
        if args.output_file:
            # Save to JSON file as array of strings
            with open(args.output_file, 'w', encoding='utf-8') as f:
                if args.pretty:
                    json.dump(combined_strings, f, indent=2, ensure_ascii=False)
                else:
                    json.dump(combined_strings, f, ensure_ascii=False)
            
            total_strings = len(combined_strings)
            print(f"Extracted {total_strings} total strings from {args.input_file}")
            print(f"Results saved to: {args.output_file}")
        else:
            # Print to stdout
            if args.pretty:
                if args.verbose:
                    print(json.dumps(output_data, indent=2, ensure_ascii=False))
                else:
                    json.dump(combined_strings, ensure_ascii=False)
            else:
                if args.verbose:
                    # Print the stringbuilder patterns
                    for sb_pattern in stringbuilder_patterns:
                        print(f"[FS] {sb_pattern.get('pattern', '')}")

                    # Print the stringbuilder identifiers
                    for sb_identifier in stringbuilder_identifiers.values():
                        print(f"[FI] {sb_identifier}")

                    # Print comments
                    for comment in comments:
                        print(f"[FC] {comment}")

                    # Print string literals
                    for string_literal in string_literals:
                        print(f"[FL] {string_literal}")
                else:
                    print(json.dumps(combined_strings, indent=2, ensure_ascii=False))

        # Success
        sys.exit(0)
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
