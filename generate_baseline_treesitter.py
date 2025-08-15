#!/usr/bin/env python3
"""
Tree-sitter based C++ parser for extracting strings and comments.
This script now acts as a wrapper around extract_strings_from_cplusplus.py.
"""

import argparse
import fnmatch
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Set, Dict, Any, Optional


class ExtractorWrapper:
    """Wrapper that calls extract_strings_from_cplusplus.py to do the actual parsing."""
    
    def __init__(self, verbose: bool = False, fail_on_error: bool = False):
        self.verbose = verbose
        self.fail_on_error = fail_on_error
        self.error_count = 0  # Track number of files that failed
        # Find the extract_strings_from_cplusplus.py script
        script_dir = Path(__file__).parent
        self.extractor_script = script_dir / "extract_strings_from_cplusplus.py"
        
        if not self.extractor_script.exists():
            raise FileNotFoundError(f"extract_strings_from_cplusplus.py not found at {self.extractor_script}")
    
    def get_error_count(self) -> int:
        """Get the number of files that failed extraction."""
        return self.error_count

    def extract_from_file(self, file_path: str) -> List[str]:
        """Extract all strings from a C++ file by calling extract_strings_from_cplusplus.py."""
        try:
            print(f"Extracting from {file_path}.")

            # Build command to call extract_strings_from_cplusplus.py
            cmd = [sys.executable, str(self.extractor_script), str(file_path)]
            
            # Run the script and capture output
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).parent)
            
            if result.returncode != 0:
                self.error_count += 1
                if self.fail_on_error:
                    print(f"❌ Error extracting from {file_path}: {result.stderr}", file=sys.stderr)
                    print(f"Command failed with exit code: {result.returncode}", file=sys.stderr)
                    sys.exit(1)
                else:
                    if self.verbose:
                        print(f"⚠️ Warning: Error extracting from {file_path}: {result.stderr}")
                        print(f"Command failed with exit code: {result.returncode}")
                        print("Continuing with other files...")
                    return []
            
            strings = json.loads(result.stdout)
            if self.verbose:
                print(f"Extracted {len(strings)} strings from {file_path}")
                print("Output was:")
                print(result.stdout)

            # Parse the JSON output
            try:                
                if isinstance(strings, list):
                    # Filter out very short strings (less than 2 words)
                    filtered_strings = []
                    for s in strings:
                        if isinstance(s, str) and len(s.split()) >= 2:
                            filtered_strings.append(s)
                    return filtered_strings
                else:
                    if self.verbose:
                        print(f"Warning: Expected list output, got {type(strings)}")
                    return []
            except json.JSONDecodeError as e:
                if self.verbose:
                    print(f"Error parsing JSON output from {file_path}: {e}")
                    print(f"Output was: {result.stdout}")
                return []
                
        except Exception as e:
            if self.verbose:
                print(f"Error running extractor on {file_path}: {e}")
            return []


def should_exclude_path(path: str, exclude_patterns: List[str]) -> bool:
    """Check if a path should be excluded based on patterns."""
    for pattern in exclude_patterns:
        # Check exact substring match
        if pattern in path:
            return True
        # Check glob-style pattern match
        if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(os.path.basename(path), pattern):
            return True
    return False


def main():
    parser = argparse.ArgumentParser(
        description='Extract strings and comments from C++ files using tree-sitter (via extract_strings_from_cplusplus.py)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s file.cpp output.json                    # Process single file
  %(prog)s src/ output.json                        # Process directory
  %(prog)s src/ output.json --exclude build        # Exclude paths containing 'build'
  %(prog)s src/ output.json --exclude "*/test/*"   # Exclude test directories (glob pattern)
  %(prog)s src/ output.json --exclude build --exclude "*.pb.h"  # Multiple exclusions
        """
    )
    parser.add_argument('input_path', help='Input C++ file or directory')
    parser.add_argument('output_file', help='Output JSON file for baseline')
    parser.add_argument('-v', '--verbose', action='store_true', 
                       help='Enable verbose output')
    parser.add_argument('--exclude', action='append', default=[], 
                       help='Exclude paths matching these patterns (can be used multiple times). '
                            'Supports both substring matching and glob patterns.')
    parser.add_argument('--no-default-excludes', action='store_true',
                       help='Disable default exclusions (build/, .git/, node_modules/, etc.)')
    parser.add_argument('--fail-on-error', action='store_true',
                       help='Fail immediately if extract_strings_from_cplusplus.py returns an error for any file. '
                            'By default, errors are logged but processing continues.')
    
    args = parser.parse_args()
    
    # Add default exclusions unless disabled
    if not args.no_default_excludes:
        default_excludes = [
            '.git/', '.svn/', '.hg/',
            'node_modules/', '__pycache__/',
            '.vscode/', '.idea/',
            'vendor/', 'third_party/', 'external/',
        ]
        args.exclude.extend(default_excludes)
    
    if args.verbose and args.exclude:
        print(f"📋 Exclusion patterns: {', '.join(args.exclude)}")
    
    if args.fail_on_error and args.verbose:
        print("⚠️ Fail-on-error mode enabled: will exit on first extraction error")
    
    extractor = ExtractorWrapper(verbose=args.verbose, fail_on_error=args.fail_on_error)
    
    if os.path.isfile(args.input_path):
        # Single file
        strings = extractor.extract_from_file(args.input_path)
    elif os.path.isdir(args.input_path):
        # Directory - find all C++ files
        strings = set()
        total_files = 0
        excluded_files = 0
        
        for root, dirs, files in os.walk(args.input_path):
            # Check if current directory should be excluded
            if should_exclude_path(root, args.exclude):
                if args.verbose:
                    print(f"🚫 Excluding directory: {root}")
                dirs[:] = []  # Don't recurse into excluded directories
                continue
                
            for file in files:
                if file.endswith(('.cpp', '.c', '.hpp', '.h', '.cc', '.cxx')):
                    file_path = os.path.join(root, file)
                    total_files += 1
                    
                    # Check if file should be excluded
                    if should_exclude_path(file_path, args.exclude):
                        excluded_files += 1
                        if args.verbose:
                            print(f"🚫 Excluding file: {file_path}")
                        continue
                    
                    if args.verbose:
                        print(f"📁 Processing file: {file_path}")
                    file_strings = extractor.extract_from_file(file_path)
                    strings.update(file_strings)
        
        strings = sorted(list(strings))
        
        if args.verbose:
            print(f"\n📊 File processing summary:")
            print(f"   Total C++ files found: {total_files}")
            print(f"   Files excluded: {excluded_files}")
            print(f"   Files processed: {total_files - excluded_files}")
            if extractor.get_error_count() > 0:
                print(f"   Files with errors: {extractor.get_error_count()}")
        
        # Warn about errors in non-verbose mode too
        if extractor.get_error_count() > 0 and not args.verbose:
            print(f"⚠️ Warning: {extractor.get_error_count()} file(s) failed extraction (use --verbose for details)")
    else:
        print(f"Error: {args.input_path} is not a valid file or directory")
        sys.exit(1)
    
    # Save results
    with open(args.output_file, 'w', encoding='utf-8') as f:
        json.dump(strings, f, indent=2, ensure_ascii=False)
    
    if args.verbose:
        print(f"\n📊 Summary: Extracted {len(strings)} unique strings")
        if extractor.get_error_count() > 0:
            print(f"⚠️ Note: {extractor.get_error_count()} file(s) had extraction errors")
        print(f"✅ Results saved to: {args.output_file}")
    else:
        print(f"✅ Baseline saved with {len(strings)} unique entries in: {args.output_file}")
        if extractor.get_error_count() > 0:
            print(f"⚠️ Note: {extractor.get_error_count()} file(s) had extraction errors")


if __name__ == '__main__':
    main()
