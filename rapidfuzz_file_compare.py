#!/usr/bin/env python3
"""
File Line Comparison using RapidFuzz

This script compares lines between two files using RapidFuzz for fast similarity matching.
It's designed to work with a smaller source file and a larger target file.
"""

import json
import argparse
import sys
from typing import List, Tuple, Dict, Any
from rapidfuzz import fuzz, process, utils


def load_file_lines(filepath: str) -> List[str]:
    """Load lines from a file, handling both JSON arrays and regular text files."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # Try to load as JSON first
            try:
                data = json.load(f)
                if isinstance(data, list):
                    # If it's a JSON array, return the elements as strings
                    return [str(item).strip() for item in data if str(item).strip()]
                else:
                    # If it's a single JSON object, convert to string
                    return [json.dumps(data, separators=(',', ':'))]
            except json.JSONDecodeError:
                # If not JSON, read as regular text file
                f.seek(0)
                lines = f.readlines()
                return [line.strip() for line in lines if line.strip()]
    except FileNotFoundError:
        print(f"Error: File '{filepath}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file '{filepath}': {e}")
        sys.exit(1)


def find_best_matches(source_lines: List[str], target_lines: List[str], 
                     similarity_threshold: float = 70.0, 
                     max_matches: int = 5) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Find the best matches for each source line in the target lines using RapidFuzz.
    
    Args:
        source_lines: Lines from the source file
        target_lines: Lines from the target file
        similarity_threshold: Minimum similarity score (0-100)
        max_matches: Maximum number of matches to return per source line
    
    Returns:
        Tuple of (results_list, unmatched_lines_list)
    """
    results = []
    unmatched_lines = []
    
    print(f"Comparing {len(source_lines)} source lines against {len(target_lines)} target lines...")
    print(f"Similarity threshold: {similarity_threshold}%")
    print("Processing... (output will be saved to JSON files)")
    
    for i, source_line in enumerate(source_lines):
        if (i + 1) % 50 == 0 or i == 0:
            print(f"Processing line {i+1}/{len(source_lines)}...")
        
        # Use RapidFuzz to find the best matches
        matches = process.extract(
            source_line, 
            target_lines, 
            scorer=fuzz.ratio,  # Using ratio for balanced similarity
            limit=max_matches,
            score_cutoff=similarity_threshold
        )
        
        if matches:
            source_result = {
                'source_line_index': i,
                'source_line': source_line,
                'matches': []
            }
            
            for match_text, score, target_index in matches:
                match_info = {
                    'target_line_index': target_index,
                    'target_line': match_text,
                    'similarity_score': round(score, 2),
                    'partial_ratio': round(fuzz.partial_ratio(source_line, match_text), 2),
                    'token_sort_ratio': round(fuzz.token_sort_ratio(source_line, match_text), 2),
                    'token_set_ratio': round(fuzz.token_set_ratio(source_line, match_text), 2)
                }
                source_result['matches'].append(match_info)
            
            results.append(source_result)
        else:
            # Add to unmatched lines
            unmatched_lines.append({
                'source_line_index': i,
                'source_line': source_line
            })
    
    return results, unmatched_lines


def print_summary_results(results: List[Dict[str, Any]], unmatched_lines: List[Dict[str, Any]], 
                         total_source_lines: int, results_file: str, unmatched_file: str):
    """Print a summary of the comparison results."""
    matched_lines = len(results)
    total_matches = sum(len(r['matches']) for r in results)
    unmatched_count = len(unmatched_lines)
    
    print("\n" + "="*60)
    print("COMPARISON SUMMARY")
    print("="*60)
    print(f"Total source lines processed: {total_source_lines}")
    print(f"Source lines with matches: {matched_lines}")
    print(f"Source lines without matches: {unmatched_count}")
    print(f"Total matches found: {total_matches}")
    
    if matched_lines > 0:
        print(f"Average matches per matched line: {total_matches/matched_lines:.1f}")
        match_rate = (matched_lines / total_source_lines) * 100
        print(f"Match rate: {match_rate:.1f}% ({matched_lines}/{total_source_lines})")
    else:
        print("Match rate: 0.0% (0 matches found)")
    
    print(f"\nOutput files:")
    print(f"  Matches: {results_file}")
    print(f"  Unmatched: {unmatched_file}")
    
    if matched_lines > 0:
        print(f"\nTop matches by similarity:")
        # Sort all matches by similarity score and show top 5
        all_matches = []
        for result in results:
            for match in result['matches']:
                all_matches.append({
                    'source_line': result['source_line'][:60] + ('...' if len(result['source_line']) > 60 else ''),
                    'target_line': match['target_line'][:60] + ('...' if len(match['target_line']) > 60 else ''),
                    'score': match['similarity_score']
                })
        
        # Sort by score and show top 5
        top_matches = sorted(all_matches, key=lambda x: x['score'], reverse=True)[:5]
        for i, match in enumerate(top_matches, 1):
            print(f"  {i}. {match['score']}% - '{match['source_line']}' → '{match['target_line']}'")
    
    if unmatched_count > 0:
        print(f"\nSample unmatched lines:")
        for i, unmatched in enumerate(unmatched_lines[:3], 1):
            line_preview = unmatched['source_line'][:80] + ('...' if len(unmatched['source_line']) > 80 else '')
            print(f"  {i}. '{line_preview}'")
        if unmatched_count > 3:
            print(f"  ... and {unmatched_count - 3} more (see {unmatched_file})")
    
    print("="*60)


def save_results_to_files(results: List[Dict[str, Any]], unmatched_lines: List[Dict[str, Any]], 
                         source_file: str, target_file: str, threshold: float) -> Tuple[str, str]:
    """Save results and unmatched lines to JSON files with auto-generated names."""
    import os
    from datetime import datetime
    
    # Generate base filename from source and target files
    source_name = os.path.splitext(os.path.basename(source_file))[0]
    target_name = os.path.splitext(os.path.basename(target_file))[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create results filename
    results_filename = f"{source_name}_vs_{target_name}_matches_{int(threshold)}pct_{timestamp}.json"
    unmatched_filename = f"{source_name}_vs_{target_name}_unmatched_{int(threshold)}pct_{timestamp}.json"
    
    # Save results
    try:
        with open(results_filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        with open(unmatched_filename, 'w', encoding='utf-8') as f:
            json.dump(unmatched_lines, f, indent=2, ensure_ascii=False)
        
        return results_filename, unmatched_filename
    except Exception as e:
        print(f"Error saving results to files: {e}")
        return None, None


def main():
    """Main function for command line use."""
    parser = argparse.ArgumentParser(
        description='Compare lines between two files using RapidFuzz for similarity matching.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s sample.json mongodb2_baseline.json
  %(prog)s sample.json mongodb2_baseline.json --threshold 80 --max-matches 3
  %(prog)s source.txt target.txt --threshold 60 --max-matches 10

Similarity Algorithms:
  - Ratio: Overall similarity between strings
  - Partial Ratio: Best matching substring similarity
  - Token Sort: Similarity after sorting tokens
  - Token Set: Similarity using set operations on tokens

Output:
  Results are automatically saved to timestamped JSON files:
  - {source}_vs_{target}_matches_{threshold}pct_{timestamp}.json
  - {source}_vs_{target}_unmatched_{threshold}pct_{timestamp}.json

Note: Files can be JSON arrays or regular text files. JSON arrays will be processed element by element.
        """
    )
    
    parser.add_argument('source_file', help='Source file (smaller file to compare from)')
    parser.add_argument('target_file', help='Target file (larger file to search in)')
    parser.add_argument('--threshold', '-t', type=float, default=70.0, metavar='SCORE',
                        help='Minimum similarity threshold (0-100, default: 70.0)')
    parser.add_argument('--max-matches', '-m', type=int, default=5, metavar='N',
                        help='Maximum matches per source line (default: 5)')
    
    args = parser.parse_args()
    
    # Validate arguments
    if not (0 <= args.threshold <= 100):
        print("Error: Threshold must be between 0 and 100")
        sys.exit(1)
    
    if args.max_matches < 1:
        print("Error: Max matches must be at least 1")
        sys.exit(1)
    
    print("=== RapidFuzz File Line Comparison ===\n")
    print(f"Source file: {args.source_file}")
    print(f"Target file: {args.target_file}")
    print(f"Similarity threshold: {args.threshold}%")
    print(f"Max matches per line: {args.max_matches}")
    print()
    
    # Load files
    print("Loading files...")
    source_lines = load_file_lines(args.source_file)
    target_lines = load_file_lines(args.target_file)
    
    print(f"Loaded {len(source_lines)} lines from source file")
    print(f"Loaded {len(target_lines)} lines from target file")
    
    if not source_lines:
        print("Error: Source file is empty or contains no valid lines")
        sys.exit(1)
    
    if not target_lines:
        print("Error: Target file is empty or contains no valid lines")
        sys.exit(1)
    
    # Find matches
    results, unmatched_lines = find_best_matches(
        source_lines, 
        target_lines, 
        args.threshold, 
        args.max_matches
    )
    
    # Save results to files
    results_file, unmatched_file = save_results_to_files(
        results, 
        unmatched_lines, 
        args.source_file, 
        args.target_file, 
        args.threshold
    )
    
    if results_file and unmatched_file:
        # Print summary
        print_summary_results(results, unmatched_lines, len(source_lines), results_file, unmatched_file)
    else:
        print("Error: Failed to save results to files")
        sys.exit(1)


if __name__ == "__main__":
    main()
