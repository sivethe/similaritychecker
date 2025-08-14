import os
import re
import sys
import json
import ast
import argparse
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
from tqdm import tqdm

CODE_EXTENSIONS = {'.py', '.js', '.ts', '.java', '.c', '.h', '.cpp', '.go', '.rb', '.rs'}

STRING_AND_COMMENT_PATTERNS = {
    'py': [r'(?P<str>["\']{1,3}.*?["\']{1,3})', r'#.*?$'],
    'js': [r'(["\'])(?:(?=(\\?))\2.)*?\1', r'//.*?$|/\*[\s\S]*?\*/'],
    'java': [r'"(?:[^"\\]|\\.)*"', r'//.*?$|/\*[\s\S]*?\*/'],
    'c': [r'"(?:[^"\\]|\\.)*"', r'//.*?$|/\*[\s\S]*?\*/'],
    'h': [r'"(?:[^"\\]|\\.)*"', r'//.*?$|/\*[\s\S]*?\*/'],
    'cpp': [r'"(?:[^"\\]|\\.)*"', r'//.*?$|/\*[\s\S]*?\*/'],
    'go': [r'"(?:[^"\\]|\\.)*"', r'//.*?$|/\*[\s\S]*?\*/'],
}

def clean_literal(s):
    try:
        s = ast.literal_eval(s)
    except Exception:
        s = s.encode('utf-8', 'ignore').decode('raw_unicode_escape', errors='ignore')

    if not isinstance(s, str):
        s = str(s)

    # Remove control characters
    s = re.sub(r'[\x00-\x1F\x7F]', '', s)

    # Remove surrogate Unicode code points (U+D800–U+DFFF)
    s = ''.join(c for c in s if not 0xD800 <= ord(c) <= 0xDFFF)

    s = s.strip()

    # Remove comment markers like #, //, /*, */
    # Handle multi-line C comments: remove /* and */ and leading * from each line
    s = re.sub(r'^\s*/\*', '', s)  # Remove /* at start
    s = re.sub(r'\*/\s*$', '', s)  # Remove */ at end
    s = re.sub(r'^\s*\*\s*', '', s, flags=re.MULTILINE)  # Remove leading * from each line
    s = re.sub(r'^\s*(#|//)', '', s, flags=re.MULTILINE)  # Remove # and // comment markers
    
    # Clean up remaining * characters that were at line beginnings
    # Replace patterns like " * " with a single space, and handle line breaks
    s = re.sub(r'\s*\*\s*', ' ', s)  # Replace " * " with single space
    s = re.sub(r'\s+', ' ', s)  # Normalize multiple spaces to single space
    
    s = s.strip()

    # Reject if line starts with non-alphanumeric character (but allow $ and %)
    if not re.match(r'^[a-zA-Z0-9$%]', s):
        return ''

    # Reject if line starts with a number
    if re.match(r'^\d', s):
        return ''

    # Reject if fewer than 4 words
    if len(s.split()) < 4:
        return ''

    return s

def extract_stringbuilder_patterns(text, verbose=False):
    """
    Extract and combine string literals from StringBuilder and str::stream() patterns.
    These patterns use << operators to concatenate strings and should be treated as combined messages.
    Returns combined strings and a set of individual strings to exclude from the final output.
    """
    combined_strings = []
    strings_to_exclude = set()
    
    # Pattern 1: Handle stream patterns (multi-line)
    # Look for various stream types followed by multiple << operations
    stream_patterns = [
        r'(?:str::stream|std::stream)\s*\(\s*\).*?(?:};|<<\s*std::endl\s*;)',  # str::stream() until closing }; or << std::endl;
        r'std::(?:cout|cerr)\s*<<[^;]+?<<[^;]+?;',  # std::cout/cerr with multiple << operations
    ]
    
    # Pattern 2: Handle uassert patterns with str::stream
    # Note: We'll handle these with custom extraction logic below instead of regex patterns
    uassert_patterns = []
    
    # Pattern 3: Handle Status constructor patterns with str::stream
    status_patterns = [
        r'Status\s*\([^,]+,\s*(str::stream\(\).*?)\)\s*;',  # Status constructor calls with str::stream expressions
    ]
    
    for stream_pattern in stream_patterns:
        for match in re.finditer(stream_pattern, text, re.DOTALL | re.MULTILINE):
            full_expression = match.group()
            
            # Extract all components (strings and variables)
            components = []
            
            # Split by << and process each part
            parts = re.split(r'\s*<<\s*', full_expression)
            for i, part in enumerate(parts[1:], 1):  # Skip the stream part (std::cout/str::stream)
                part = part.strip().rstrip(';')
                
                # Check if this is a string literal or contains multiple adjacent string literals
                string_matches = list(re.finditer(r'"([^"]*)"', part))
                if string_matches:
                    # Handle multiple adjacent string literals (C++ auto-concatenation)
                    for string_match in string_matches:
                        string_content = string_match.group(1)
                        if string_content:
                            components.append(string_content)
                            # Only exclude from normal processing if this is part of a multi-component pattern
                            # We'll decide this later when we know the full component count
                else:
                    # This is a variable - represent as %s (but skip std::endl and similar)
                    if part and not part.startswith('std::') and part != 'std::endl':
                        components.append('%s')
            
            # Combine if we have multiple components with at least one string
            string_components = [c for c in components if c != '%s']
            if len(components) > 1 and string_components:
                # This is a multi-component pattern - exclude individual strings
                for component in string_components:
                    strings_to_exclude.add(component.strip())
                
                combined = ''.join(components)
                combined = re.sub(r'\s+', ' ', combined.strip())
                
                if combined and len(combined.split()) >= 4:
                    combined_strings.append(combined)
                    
                    if verbose:
                        match_start = match.start()
                        line_num = text[:match_start].count('\n') + 1
                        print(f"    🔗 Combined {len(components)} components in stream pattern at line {line_num}: {combined[:80]}{'...' if len(combined) > 80 else ''}")
            
            # Also handle simple case of just one meaningful string literal (e.g., std::cerr << "message" << std::endl)
            elif len(string_components) == 1 and len(components) == 1:
                # Single string case - don't exclude it, let normal processing handle it
                pass
            
            # Also handle simple case of just string literals without variables
            elif len(string_components) > 1:
                # This is a multi-string pattern - exclude individual strings
                for component in string_components:
                    strings_to_exclude.add(component.strip())
                
                combined = ' '.join(string_components).strip()
                combined = re.sub(r'\s+', ' ', combined)
                
                if combined and len(combined.split()) >= 4:
                    combined_strings.append(combined)
                    
                    if verbose:
                        match_start = match.start()
                        line_num = text[:match_start].count('\n') + 1
                        print(f"    🔗 Combined {len(string_components)} strings in stream pattern at line {line_num}: {combined[:80]}{'...' if len(combined) > 80 else ''}")
    
    # Extract uassert patterns with custom logic for proper balanced parentheses
    def extract_uassert_streams(content):
        """Extract stream expressions from uassert/uasserted calls with proper parentheses balancing"""
        results = []
        
        # Find all uassert and uasserted calls
        for call_type in ['uassert', 'uasserted']:
            pos = 0
            while True:
                pos = content.find(call_type, pos)
                if pos == -1:
                    break
                
                # Check if this is a word boundary (not part of another word)
                if pos > 0 and content[pos-1].isalnum():
                    pos += 1
                    continue
                
                # Find the opening parenthesis
                paren_pos = content.find('(', pos)
                if paren_pos == -1:
                    pos += 1
                    continue
                
                # Extract the full call with balanced parentheses
                paren_count = 0
                end_pos = paren_pos
                while end_pos < len(content):
                    if content[end_pos] == '(':
                        paren_count += 1
                    elif content[end_pos] == ')':
                        paren_count -= 1
                        if paren_count == 0:
                            # Found the end of call
                            full_call = content[pos:end_pos+1]
                            
                            # Extract arguments by finding commas at the right level
                            args = []
                            current_arg = ""
                            paren_level = 0
                            inside_quotes = False
                            escape_next = False
                            
                            # Start after opening parenthesis
                            for i, char in enumerate(full_call[full_call.find('(')+1:-1]):
                                if escape_next:
                                    current_arg += char
                                    escape_next = False
                                    continue
                                
                                if char == '\\':
                                    escape_next = True
                                    current_arg += char
                                    continue
                                
                                if char == '"' and not escape_next:
                                    inside_quotes = not inside_quotes
                                    current_arg += char
                                    continue
                                
                                if inside_quotes:
                                    current_arg += char
                                    continue
                                
                                if char == '(':
                                    paren_level += 1
                                elif char == ')':
                                    paren_level -= 1
                                elif char == ',' and paren_level == 0:
                                    # Found argument separator
                                    args.append(current_arg.strip())
                                    current_arg = ""
                                    continue
                                
                                current_arg += char
                            
                            # Add the last argument
                            if current_arg:
                                args.append(current_arg.strip())
                            
                            # For uassert: args[1] should be the stream expression
                            # For uasserted: args[1] should be the stream expression
                            if len(args) >= 2 and 'str::stream()' in args[1]:
                                results.append(args[1])
                            
                            break
                    end_pos += 1
                
                pos += 1
        
        return results
    
    # Process extracted uassert stream expressions
    uassert_streams = extract_uassert_streams(text)
    for stream_expression in uassert_streams:
        # Extract all components (strings and variables) from the stream expression
        components = []
        
        # Split by << and process each part
        parts = re.split(r'\s*<<\s*', stream_expression)
        for i, part in enumerate(parts[1:], 1):  # Skip the stream part (str::stream)
            part = part.strip()
            
            # Check if this is a string literal or contains string literals
            string_matches = list(re.finditer(r'"([^"]*)"', part))
            if string_matches:
                # Handle multiple adjacent string literals (C++ auto-concatenation)
                for string_match in string_matches:
                    string_content = string_match.group(1)
                    if string_content:
                        components.append(string_content)
            else:
                # This is a variable - represent as %s (but skip std::endl and similar)
                part_clean = part.rstrip('";')
                if part_clean and not part_clean.startswith('std::'):
                    components.append('%s')
        
        # Combine if we have multiple components with at least one string
        string_components = [c for c in components if c != '%s']
        if len(components) > 1 and string_components:
            # This is a multi-component pattern - exclude individual strings
            for component in string_components:
                # Apply the same cleaning as main extraction to ensure exclusion works
                try:
                    cleaned_component = clean_literal(f'"{component}"')
                except:
                    cleaned_component = component
                strings_to_exclude.add(cleaned_component.strip())
            
            combined = ''.join(components)
            combined = re.sub(r'\s+', ' ', combined)
            
            if combined and len(combined.split()) >= 3:
                combined_strings.append(combined)
                
                if verbose:
                    print(f"    🔧 Extracted uassert stream pattern: {combined[:80]}{'...' if len(combined) > 80 else ''}")

    # Process Status constructor patterns with str::stream
    for status_pattern in status_patterns:
        for match in re.finditer(status_pattern, text, re.DOTALL | re.MULTILINE):
            stream_expression = match.group(1)  # Extract the str::stream part
            
            # Extract all components (strings and variables) from the stream expression
            components = []
            
            # Split by << and process each part
            parts = re.split(r'\s*<<\s*', stream_expression)
            for i, part in enumerate(parts[1:], 1):  # Skip the stream part (str::stream)
                part = part.strip()
                
                # Check if this is a string literal or contains string literals
                string_matches = list(re.finditer(r'"([^"]*)"', part))
                if string_matches:
                    # Handle multiple adjacent string literals (C++ auto-concatenation)
                    for string_match in string_matches:
                        # Get the full match including quotes, then extract content to preserve escape sequences
                        full_match = string_match.group(0)  # includes quotes
                        string_content = full_match[1:-1]   # remove quotes, preserve escape sequences as they appear in source
                        if string_content:
                            components.append(string_content)
                else:
                    # This is a variable - represent as %s (but skip std::endl and similar)
                    part_clean = part.rstrip('";')
                    if part_clean and not part_clean.startswith('std::'):
                        components.append('%s')
            
            # Combine if we have multiple components with at least one string
            string_components = [c for c in components if c != '%s']
            if len(components) > 1 and string_components:
                # This is a multi-component pattern - exclude individual strings
                for component in string_components:
                    # Apply the same cleaning as main extraction to ensure exclusion works
                    try:
                        cleaned_component = clean_literal(f'"{component}"')
                    except:
                        cleaned_component = component
                    strings_to_exclude.add(cleaned_component.strip())
                
                combined = ''.join(components)
                combined = re.sub(r'\s+', ' ', combined.strip())
                
                if combined and len(combined.split()) >= 4:
                    combined_strings.append(combined)
                    
                    if verbose:
                        match_start = match.start()
                        line_num = text[:match_start].count('\n') + 1
                        print(f"    🔗 Combined {len(components)} components in Status stream pattern at line {line_num}: {combined[:80]}{'...' if len(combined) > 80 else ''}")

    # Pattern 2: Handle StringBuilder variable patterns
    # Find StringBuilder variable declarations and track their << operations
    sb_variable_pattern = r'(?:auto|StringBuilder)\s+(\w+)\s*(?:=\s*StringBuilder\s*\(\s*\))?\s*;?'
    
    for match in re.finditer(sb_variable_pattern, text):
        var_name = match.group(1)
        match_end = match.end()
        
        # Look for subsequent << operations with this variable in the remaining text
        # Expand scope to capture more of the StringBuilder usage
        remaining_text = text[match_end:match_end + 3000]  # Larger scope for complex patterns
        
        # Split into lines for analysis
        lines = remaining_text.split('\n')
        
        # Find all StringBuilder operations and their conditional context
        operations_by_branch = {}  # branch_id -> operations
        current_branch = 'main'
        branch_counter = 0
        
        for line_idx, line in enumerate(lines):
            line_stripped = line.strip()
            
            # Detect conditional branches
            if f'{var_name} <<' in line_stripped:
                # Check if this line is in a conditional context
                # Look backwards a few lines to see if we're in an if/else block
                context_lines = lines[max(0, line_idx-5):line_idx]
                context = ' '.join(l.strip() for l in context_lines)
                
                # Determine branch context
                if 'if (' in context and line_idx > 0:
                    # Look at the previous few lines for if/else context
                    prev_line = lines[line_idx-1].strip() if line_idx > 0 else ""
                    if 'else' in prev_line or any('else' in l for l in context_lines[-3:]):
                        current_branch = f'else_{branch_counter}'
                    else:
                        current_branch = f'if_{branch_counter}'
                        branch_counter += 1
                
                # Extract operations from this line
                parts = line_stripped.split('<<')
                line_operations = []
                
                for i, part in enumerate(parts[1:], 1):  # Skip the variable part
                    part = part.strip().rstrip(';')
                    
                    # Check if this part starts with a string literal
                    string_match = re.match(r'"([^"]*)"', part)
                    if string_match:
                        string_content = string_match.group(1)
                        line_operations.append(string_content)
                        strings_to_exclude.add(string_content.strip())
                        
                        # Check if there's more after the string
                        remaining_part = part[string_match.end():].strip()
                        if remaining_part.startswith('<<'):
                            line_operations.append('%s')
                    else:
                        # This is a function call or variable - represent as %s
                        line_operations.append('%s')
                
                # Add to the appropriate branch
                if current_branch not in operations_by_branch:
                    operations_by_branch[current_branch] = []
                operations_by_branch[current_branch].extend(line_operations)
        
        # Process each branch separately
        for branch_name, branch_operations in operations_by_branch.items():
            if branch_operations:
                combined = ''.join(branch_operations)
                combined = re.sub(r'\s+', ' ', combined.strip())
                
                has_text = any(op for op in branch_operations if op != '%s' and len(op.strip()) > 0)
                if combined and has_text and len(combined.split()) >= 2:
                    combined_strings.append(combined)
                    
                    if verbose:
                        match_start = match.start()
                        line_num = text[:match_start].count('\n') + 1
                        print(f"    🔗 StringBuilder pattern from variable '{var_name}' branch '{branch_name}': {combined[:80]}{'...' if len(combined) > 80 else ''}")
    
    return combined_strings, strings_to_exclude

def combine_function_call_strings(text, matches, match_info, verbose=False):
    """
    Find and combine multiple string literals inside function calls like errmsg() and errdetail_log().
    These functions often have multiple string literals that should be treated as one combined string.
    Returns combined strings and a set of individual strings to exclude from the final output.
    """
    combined_strings = []
    strings_to_exclude = set()
    
    # Pattern to find function calls with multiple string literals
    # Matches: errmsg( ... ) or errdetail_log( ... ) containing multiple quoted strings
    function_pattern = r'(errmsg|errdetail_log)\s*\(\s*([^;]+?)\)\s*[,;]'
    
    for match in re.finditer(function_pattern, text, re.DOTALL | re.MULTILINE):
        func_name = match.group(1)
        func_content = match.group(2)
        
        # Extract all string literals from within this function call
        string_literals = []
        string_pattern = r'"(?:[^"\\]|\\.)*"'
        
        for string_match in re.finditer(string_pattern, func_content):
            string_literal = string_match.group()
            try:
                # Clean and evaluate the string literal
                cleaned = clean_literal(string_literal)
                if cleaned:
                    string_literals.append(cleaned)
            except:
                # If we can't parse it, just strip quotes and basic cleanup
                cleaned = string_literal.strip('"').replace('\\"', '"').replace('\\\\', '\\')
                if cleaned:
                    string_literals.append(cleaned)
        
        # If we found multiple string literals in this function call, combine them
        if len(string_literals) > 1:
            # Combine the strings with spaces
            combined = ' '.join(string_literals).strip()
            
            # Apply additional cleaning
            combined = re.sub(r'\s+', ' ', combined)  # Normalize whitespace
            
            if combined and len(combined.split()) >= 4:  # Meet minimum word requirement
                combined_strings.append(combined)
                
                # Only exclude individual strings when we're actually combining multiple strings
                for literal in string_literals:
                    strings_to_exclude.add(literal)
                
                if verbose:
                    # Find line number of the function call
                    match_start = match.start()
                    line_num = text[:match_start].count('\n') + 1
                    print(f"    🔗 Combined {len(string_literals)} strings in {func_name}() at line {line_num}: {combined[:80]}{'...' if len(combined) > 80 else ''}")
        # If there's only one string literal, don't exclude it - let it be processed normally
    
    return combined_strings, strings_to_exclude

def extract_strings_and_comments(filepath, verbose=False):
    ext = filepath.suffix[1:]
    patterns = STRING_AND_COMMENT_PATTERNS.get(ext)
    if not patterns:
        return []

    if verbose:
        print(f"  📁 Processing file: {filepath}")

    try:
        text = filepath.read_text(encoding='utf-8', errors='ignore')
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return []

    matches = []
    match_info = []  # Store (line_number, cleaned_string) for verbose output
    lines = text.split('\n')
    
    # Process each pattern
    for pattern in patterns:
        # For string patterns (those starting with "), process line by line to avoid cross-line issues
        if pattern.startswith('"'):
            for line_num, line in enumerate(lines, 1):
                for match in re.finditer(pattern, line):
                    result = match.group()
                    if isinstance(result, tuple):
                        result = "".join(result)
                    
                    cleaned = clean_literal(result)
                    if cleaned:
                        matches.append(cleaned)
                        if verbose:
                            match_info.append((line_num, cleaned))
        else:
            # For comment patterns, use the full text to handle multi-line comments
            for match in re.finditer(pattern, text, flags=re.MULTILINE | re.DOTALL):
                result = match.group()
                if isinstance(result, tuple):
                    result = "".join(result)
                
                cleaned = clean_literal(result)
                if cleaned:
                    matches.append(cleaned)
                    if verbose:
                        # Find the line number where this match starts
                        match_start = match.start()
                        line_num = text[:match_start].count('\n') + 1
                        match_info.append((line_num, cleaned))

    # Post-process to combine concatenated strings in function calls like errmsg() and errdetail_log()
    combined_matches, strings_to_exclude = combine_function_call_strings(text, matches, match_info, verbose)
    
    # Also extract StringBuilder patterns
    stringbuilder_matches, stringbuilder_exclude = extract_stringbuilder_patterns(text, verbose)
    
    # Combine all exclusions
    all_exclusions = strings_to_exclude.union(stringbuilder_exclude)
    
    # Filter out individual strings that are part of combined expressions
    filtered_matches = [match for match in matches if match not in all_exclusions]
    
    # Add the combined strings from both function calls and StringBuilder patterns
    if combined_matches:
        filtered_matches.extend(combined_matches)
    if stringbuilder_matches:
        filtered_matches.extend(stringbuilder_matches)

    if verbose and filtered_matches:
        print(f"    ✓ Extracted {len(filtered_matches)} strings/comments:")
        # Update match_info to reflect filtered results
        filtered_match_info = [(line_num, match) for line_num, match in match_info if match not in all_exclusions]
        for line_num, match in filtered_match_info:
            print(f"      Line {line_num}: {match[:80]}{'...' if len(match) > 80 else ''}")
        
        # Also show the combined StringBuilder strings
        if stringbuilder_matches:
            print(f"    ✓ Added {len(stringbuilder_matches)} combined StringBuilder strings")
    elif verbose:
        print(f"    ✗ No valid strings/comments found")

    return filtered_matches

def extract_repo_strings(repo_path, verbose=False):
    all_strings = set()
    files_processed = 0
    
    repo_path = Path(repo_path)
    
    if verbose:
        if repo_path.is_file():
            print(f"🔍 Starting extraction from file: {repo_path}")
        else:
            print(f"🔍 Starting extraction from directory: {repo_path}")
    
    # Handle single file input
    if repo_path.is_file():
        if repo_path.suffix in CODE_EXTENSIONS:
            files_processed = 1
            strings = extract_strings_and_comments(repo_path, verbose)
            all_strings.update(strings)
        elif verbose:
            print(f"⚠️  File {repo_path} has unsupported extension. Supported extensions: {', '.join(sorted(CODE_EXTENSIONS))}")
    
    # Handle directory input
    elif repo_path.is_dir():
        for path in repo_path.rglob('*'):
            if path.suffix in CODE_EXTENSIONS:
                files_processed += 1
                strings = extract_strings_and_comments(path, verbose)
                all_strings.update(strings)
    
    if verbose:
        if repo_path.is_file():
            print(f"📊 Summary: Processed 1 file, found {len(all_strings)} unique strings/comments")
        else:
            print(f"📊 Summary: Processed {files_processed} files, found {len(all_strings)} unique strings/comments")
    
    return sorted(all_strings)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract strings and comments from code files to create a baseline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_baseline.py /path/to/repo baseline.json
  python generate_baseline.py /path/to/single/file.py baseline.json
  python generate_baseline.py /path/to/repo baseline.json --verbose
  python generate_baseline.py /path/to/file.js baseline.json -v
        """
    )
    
    parser.add_argument("repo_path", 
                       help="Path to the repository directory or single code file to analyze")
    parser.add_argument("baseline_file", 
                       help="Output file for the baseline JSON")
    parser.add_argument("-v", "--verbose", 
                       action="store_true",
                       help="Enable verbose output showing files processed and extracted strings")
    
    args = parser.parse_args()
    
    repo_path = Path(args.repo_path)
    baseline_file = args.baseline_file
    verbose = args.verbose

    if not repo_path.exists():
        print(f"❌ Error: Path does not exist: {repo_path}")
        sys.exit(1)

    if repo_path.is_file():
        print(f"🔍 Extracting strings/comments from file: {repo_path}")
    else:
        print(f"🔍 Extracting strings/comments from directory: {repo_path}")
    
    if verbose:
        print("🔧 Verbose mode enabled - showing detailed processing information")
    
    extracted_strings = extract_repo_strings(repo_path, verbose)

    with open(baseline_file, 'w', encoding='utf-8') as f:
        json.dump(extracted_strings, f, indent=2, ensure_ascii=False)

    print(f"✅ Baseline saved with {len(extracted_strings)} unique cleaned entries in: {baseline_file}")
