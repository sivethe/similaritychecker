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
    
    # Filter out individual strings that are part of combined function calls
    filtered_matches = [match for match in matches if match not in strings_to_exclude]
    
    # Add the combined strings
    if combined_matches:
        filtered_matches.extend(combined_matches)

    if verbose and filtered_matches:
        print(f"    ✓ Extracted {len(filtered_matches)} strings/comments:")
        # Update match_info to reflect filtered results
        filtered_match_info = [(line_num, match) for line_num, match in match_info if match not in strings_to_exclude]
        for line_num, match in filtered_match_info:
            print(f"      Line {line_num}: {match[:80]}{'...' if len(match) > 80 else ''}")
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
