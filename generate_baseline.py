import os
import re
import sys
import json
import ast
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
from tqdm import tqdm

CODE_EXTENSIONS = {'.py', '.js', '.ts', '.java', '.c', '.h', '.cpp', '.go', '.rb', '.rs'}

STRING_AND_COMMENT_PATTERNS = {
    'py': [r'(?P<str>["\']{1,3}.*?["\']{1,3})', r'#.*?$'],
    'js': [r'(["\'])(?:(?=(\\?))\2.)*?\1', r'//.*?$|/\*[\s\S]*?\*/'],
    'java': [r'"(?:\\.|[^"\\])*"', r'//.*?$|/\*[\s\S]*?\*/'],
    'c': [r'"(?:\\.|[^"\\])*"', r'//.*?$|/\*[\s\S]*?\*/'],
    'h': [r'"(?:\\.|[^"\\])*"', r'//.*?$|/\*[\s\S]*?\*/'],
    'cpp': [r'"(?:\\.|[^"\\])*"', r'//.*?$|/\*[\s\S]*?\*/'],
    'go': [r'"(?:\\.|[^"\\])*"', r'//.*?$|/\*[\s\S]*?\*/'],
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
    s = re.sub(r'^\s*(#|//|/\*|\*/)', '', s).strip()

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

def extract_strings_and_comments(filepath):
    ext = filepath.suffix[1:]
    patterns = STRING_AND_COMMENT_PATTERNS.get(ext)
    if not patterns:
        return []

    try:
        text = filepath.read_text(encoding='utf-8', errors='ignore')
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return []

    matches = []
    for pattern in patterns:
        results = re.findall(pattern, text, flags=re.MULTILINE)
        for result in results:
            if isinstance(result, tuple):
                result = "".join(result)
            cleaned = clean_literal(result)
            if cleaned:
                matches.append(cleaned)

    return matches

def extract_repo_strings(repo_path):
    all_strings = set()
    for path in Path(repo_path).rglob('*'):
        if path.suffix in CODE_EXTENSIONS:
            strings = extract_strings_and_comments(path)
            all_strings.update(strings)
    return sorted(all_strings)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python generate_baseline.py <reference_repo_path> <baseline_output_file>")
        sys.exit(1)

    repo_path = Path(sys.argv[1])
    baseline_file = sys.argv[2]

    print(f"🔍 Extracting strings/comments from: {repo_path}")
    extracted_strings = extract_repo_strings(repo_path)

    with open(baseline_file, 'w', encoding='utf-8') as f:
        json.dump(extracted_strings, f, indent=2, ensure_ascii=False)

    print(f"✅ Baseline saved with {len(extracted_strings)} unique cleaned entries in: {baseline_file}")
