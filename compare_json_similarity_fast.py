import json
import argparse
from fuzzywuzzy import fuzz
from rapidfuzz import fuzz as rapid_fuzz
from tqdm import tqdm
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from functools import partial

def load_json_lines(file_path):
    """Loads a JSON array of strings from a file."""
    with open(file_path, 'r') as f:
        data = json.load(f)
        if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
            raise ValueError(f"Expected a JSON array of strings in {file_path}")
        return data


def compare_single_source_line(args):
    """Compare a single source line against all target lines."""
    source_idx, source_line, target_data, threshold = args
    matches = []
    
    # Pre-filter by length for this source line
    source_len = len(source_line)
    min_len = 3
    
    for target_idx, target_line in enumerate(target_data):
        if len(target_line) < min_len:
            continue
            
        target_len = len(target_line)
        
        # Quick length-based filter: if strings are very different in length,
        # they're unlikely to have high similarity
        length_ratio = min(source_len, target_len) / max(source_len, target_len)
        if length_ratio < 0.5 and threshold > 60:  # Adjust threshold as needed
            continue
        
        # Use rapidfuzz for better performance
        score = rapid_fuzz.token_sort_ratio(source_line, target_line)
        if score >= threshold:
            matches.append({
                "target_index": target_idx,
                "similarity_score": score,
                "target_line": target_line
            })
    
    # Return grouped result for this source line
    if matches:
        # Sort matches by similarity score (highest first)
        matches.sort(key=lambda x: x["similarity_score"], reverse=True)
        return {
            "source_index": source_idx,
            "source_line": source_line,
            "target_matches": matches,
            "match_count": len(matches)
        }
    return None


def compare_json_lines_parallel(source_data, target_data, threshold=80, max_workers=None):
    """Parallel version of compare_json_lines using multiprocessing."""
    if max_workers is None:
        max_workers = min(multiprocessing.cpu_count(), len(source_data))
    
    print(f"Processing {len(source_data)} source lines against {len(target_data)} target lines...")
    print(f"Using {max_workers} parallel workers...")
    
    # Pre-filter source data
    min_len = 3
    filtered_source = [(i, line) for i, line in enumerate(source_data) if len(line) >= min_len]
    
    # Prepare arguments for parallel processing
    args_list = [(i, source_line, target_data, threshold) 
                 for i, source_line in filtered_source]
    
    matched_lines = []
    
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        futures = [executor.submit(compare_single_source_line, args) for args in args_list]
        
        # Collect results with progress bar
        for future in tqdm(futures, desc="Comparing lines", unit="line"):
            result = future.result()
            if result:  # Only add if there were matches
                matched_lines.append(result)
    
    # Sort by source index to maintain order
    matched_lines.sort(key=lambda x: x["source_index"])
    return matched_lines


def compare_json_lines_optimized(source_data, target_data, threshold=80):
    """Optimized single-threaded version with early termination and caching."""
    matched_lines = []
    print(f"Processing {len(source_data)} source lines against {len(target_data)} target lines...")
    
    # Pre-filter very short strings that are unlikely to match
    min_len = 3
    filtered_target = [(i, line) for i, line in enumerate(target_data) if len(line) >= min_len]
    
    for i, source_line in enumerate(tqdm(source_data, desc="Comparing lines", unit="line")):
        if len(source_line) < min_len:
            continue
            
        source_len = len(source_line)
        target_matches = []
        
        for j, target_line in filtered_target:
            target_len = len(target_line)
            
            # Quick length-based filter: if strings are very different in length,
            # they're unlikely to have high similarity
            length_ratio = min(source_len, target_len) / max(source_len, target_len)
            if length_ratio < 0.5 and threshold > 60:  # Adjust threshold as needed
                continue
            
            # Use rapidfuzz for better performance
            score = rapid_fuzz.token_sort_ratio(source_line, target_line)
            if score >= threshold:
                target_matches.append({
                    "target_index": j,
                    "similarity_score": score,
                    "target_line": target_line
                })
        
        # Only add if there were matches
        if target_matches:
            # Sort matches by similarity score (highest first)
            target_matches.sort(key=lambda x: x["similarity_score"], reverse=True)
            matched_lines.append({
                "source_index": i,
                "source_line": source_line,
                "target_matches": target_matches,
                "match_count": len(target_matches)
            })
    
    return matched_lines


def compare_json_lines_ultra_fast(source_data, target_data, threshold=80, batch_size=1000):
    """Ultra-fast version with advanced optimizations."""
    matched_lines = []
    print(f"Processing {len(source_data)} source lines against {len(target_data)} target lines...")
    print("Using ultra-fast algorithm with advanced optimizations...")
    
    # Pre-filter and create lookup structures
    min_len = 3
    filtered_source = [(i, line) for i, line in enumerate(source_data) if len(line) >= min_len]
    filtered_target = [(i, line) for i, line in enumerate(target_data) if len(line) >= min_len]
    
    # Group by approximate length for faster filtering
    from collections import defaultdict
    target_by_length = defaultdict(list)
    for idx, line in filtered_target:
        length_bucket = len(line) // 10  # Group by tens of characters
        target_by_length[length_bucket].append((idx, line))
    
    for source_idx, source_line in tqdm(filtered_source, desc="Comparing lines", unit="line"):
        source_len = len(source_line)
        source_bucket = source_len // 10
        target_matches = []
        
        # Only compare with similar-length targets (expand search range based on threshold)
        search_range = 2 if threshold > 80 else 3
        for bucket in range(max(0, source_bucket - search_range), source_bucket + search_range + 1):
            for target_idx, target_line in target_by_length[bucket]:
                target_len = len(target_line)
                
                # More precise length filtering
                length_ratio = min(source_len, target_len) / max(source_len, target_len)
                if length_ratio < (0.6 if threshold > 80 else 0.4):
                    continue
                
                # Use rapidfuzz for better performance
                score = rapid_fuzz.token_sort_ratio(source_line, target_line)
                if score >= threshold:
                    target_matches.append({
                        "target_index": target_idx,
                        "similarity_score": score,
                        "target_line": target_line
                    })
        
        # Only add if there were matches
        if target_matches:
            # Sort matches by similarity score (highest first)
            target_matches.sort(key=lambda x: x["similarity_score"], reverse=True)
            matched_lines.append({
                "source_index": source_idx,
                "source_line": source_line,
                "target_matches": target_matches,
                "match_count": len(target_matches)
            })
    
    return matched_lines


def main():
    parser = argparse.ArgumentParser(description="Match lines between two JSONL files using fuzzy similarity.")
    parser.add_argument("source", help="Path to the source JSON lines file.")
    parser.add_argument("target", help="Path to the target JSON lines file.")
    parser.add_argument("--threshold", type=int, default=80, help="Similarity threshold (default=80).")
    parser.add_argument("--parallel", action="store_true", help="Use parallel processing for faster comparison.")
    parser.add_argument("--ultra-fast", action="store_true", help="Use ultra-fast algorithm with advanced optimizations.")
    parser.add_argument("--workers", type=int, default=None, help="Number of parallel workers (default: auto).")
    parser.add_argument("--output", "-o", help="Output JSON file to write matches (default: print to console).")
    parser.add_argument("--pretty", action="store_true", help="Pretty print JSON output with indentation.")

    args = parser.parse_args()

    source_data = load_json_lines(args.source)
    target_data = load_json_lines(args.target)

    if args.ultra_fast:
        matches = compare_json_lines_ultra_fast(source_data, target_data, args.threshold)
    elif args.parallel:
        matches = compare_json_lines_parallel(source_data, target_data, args.threshold, args.workers)
    else:
        matches = compare_json_lines_optimized(source_data, target_data, args.threshold)

    print(f"\nFound matches for {len(matches)} source lines with similarity >= {args.threshold}%")
    
    # Calculate total match count
    total_matches = sum(match["match_count"] for match in matches)
    print(f"Total target matches: {total_matches}")
    
    if args.output:
        # Write to JSON file
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                if args.pretty:
                    json.dump(matches, f, indent=2, ensure_ascii=False)
                else:
                    json.dump(matches, f, ensure_ascii=False)
            print(f"✅ Results written to: {args.output}")
        except Exception as e:
            print(f"❌ Error writing to file {args.output}: {e}")
            return 1
    else:
        # Print to console
        for match in matches:
            if args.pretty:
                print(json.dumps(match, indent=2, ensure_ascii=False))
            else:
                print(json.dumps(match, ensure_ascii=False))

if __name__ == "__main__":
    main()
