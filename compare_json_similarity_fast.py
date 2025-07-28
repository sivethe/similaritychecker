import json
import argparse
from tqdm import tqdm
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from functools import partial
import itertools
import re

def load_json_lines(file_path):
    """Loads a JSON array of strings from a file."""
    with open(file_path, 'r') as f:
        data = json.load(f)
        if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
            raise ValueError(f"Expected a JSON array of strings in {file_path}")
        return data


def normalize_text(text):
    """Normalize text for comparison by removing extra whitespace and converting to lowercase."""
    return ' '.join(text.lower().split())

def has_format_specifiers(text):
    """Check if text contains C printf style format specifiers."""
    # Common C printf format specifiers
    format_pattern = r'%[-#+ 0]*\*?(?:\d+|\*)?(?:\.(?:\d+|\*))?[hlL]?[diouxXeEfFgGaAcspn%]'
    return bool(re.search(format_pattern, text))

def convert_to_regex_pattern(text):
    """Convert a string with format specifiers to a regex pattern."""
    # First identify and temporarily replace format specifiers with placeholders
    format_pattern = r'%[-#+ 0]*\*?(?:\d+|\*)?(?:\.(?:\d+|\*))?[hlL]?[diouxXeEfFgGaAcspn%]'
    specifiers = re.findall(format_pattern, text)
    
    # Replace format specifiers with unique placeholders
    temp_text = text
    placeholder_map = {}
    for i, spec in enumerate(specifiers):
        placeholder = f"__PLACEHOLDER_{i}__"
        temp_text = temp_text.replace(spec, placeholder, 1)
        placeholder_map[placeholder] = spec
    
    # Escape the text (now without format specifiers)
    escaped_text = re.escape(temp_text)
    
    # Define regex patterns for different format specifier types
    format_replacements = {
        '%s': r'.*?',       # String: any characters (non-greedy)
        '%d': r'[+-]?\d+',  # Integer
        '%i': r'[+-]?\d+',  # Integer
        '%o': r'[0-7]+',    # Octal
        '%u': r'\d+',       # Unsigned integer
        '%x': r'[0-9a-fA-F]+',  # Hexadecimal (lowercase)
        '%X': r'[0-9a-fA-F]+',  # Hexadecimal (uppercase)
        '%f': r'[+-]?\d*\.?\d+(?:[eE][+-]?\d+)?',  # Float
        '%F': r'[+-]?\d*\.?\d+(?:[eE][+-]?\d+)?',  # Float
        '%e': r'[+-]?\d*\.?\d+(?:[eE][+-]?\d+)?',  # Scientific notation
        '%E': r'[+-]?\d*\.?\d+(?:[eE][+-]?\d+)?',  # Scientific notation
        '%g': r'[+-]?\d*\.?\d+(?:[eE][+-]?\d+)?',  # General float
        '%G': r'[+-]?\d*\.?\d+(?:[eE][+-]?\d+)?',  # General float
        '%c': r'.',         # Single character
        '%p': r'0x[0-9a-fA-F]+',  # Pointer
        '%%': r'%'          # Literal %
    }
    
    # Replace placeholders with appropriate regex patterns
    result_pattern = escaped_text
    for placeholder, original_spec in placeholder_map.items():
        # Extract the base specifier (last character)
        base_spec = original_spec[-1]
        
        # Handle %% special case
        if original_spec == '%%':
            regex_replacement = format_replacements['%%']
        else:
            # Map base specifier to regex pattern
            base_key = f'%{base_spec}'
            regex_replacement = format_replacements.get(base_key, r'[^\s]*')  # Default to string-like
        
        escaped_placeholder = re.escape(placeholder)
        result_pattern = result_pattern.replace(escaped_placeholder, regex_replacement)
    
    return result_pattern

def is_format_specifier_match(source, target):
    """
    Check if source (with format specifiers) matches target.
    Returns (is_match, match_type, matched_text, similarity_score).
    """
    if not has_format_specifiers(source):
        return False, "no_format_match", "", 0.0
    
    source_norm = normalize_text(source)
    target_norm = normalize_text(target)
    
    # Convert source to regex pattern
    try:
        pattern = convert_to_regex_pattern(source_norm)
        regex = re.compile(pattern, re.IGNORECASE)
        
        # Check if the entire target matches the pattern
        if regex.fullmatch(target_norm):
            # Calculate similarity score based on how much is literal vs format specifiers
            literal_chars = len(re.sub(r'%[-#+ 0]*\*?(?:\d+|\*)?(?:\.(?:\d+|\*))?[hlL]?[diouxXeEfFgGaAcspn%]', '', source_norm))
            total_chars = len(source_norm)
            if total_chars > 0:
                score = (literal_chars / total_chars) * 100
                # Bonus for exact length match
                if len(source_norm.split()) == len(target_norm.split()):
                    score = min(100.0, score + 20)
            else:
                score = 50.0  # Default score for pattern-only matches
            
            return True, "format_specifier_match", source_norm, score
        
    except re.error:
        # If regex compilation fails, fall back to no match
        pass
    
    return False, "no_format_match", "", 0.0

def get_word_combinations(text, min_words=4):
    """Get all combinations of consecutive words from text with minimum word count."""
    words = text.split()
    combinations = []
    
    # Get all consecutive word combinations from min_words to total words
    for length in range(min_words, len(words) + 1):
        for start in range(len(words) - length + 1):
            combination = ' '.join(words[start:start + length])
            combinations.append(combination)
    
    return combinations

def is_substring_match(source, target, min_words=4):
    """
    Check if source and target have substring matches.
    Returns (is_match, match_type, matched_text, similarity_score).
    """
    source_norm = normalize_text(source)
    target_norm = normalize_text(target)
    
    # First check for format specifier matches
    is_format_match, format_match_type, format_matched_text, format_score = is_format_specifier_match(source, target)
    if is_format_match:
        return True, format_match_type, format_matched_text, format_score
    
    # Also check reverse direction for format specifiers
    is_reverse_format_match, reverse_format_match_type, reverse_format_matched_text, reverse_format_score = is_format_specifier_match(target, source)
    if is_reverse_format_match:
        return True, "reverse_" + reverse_format_match_type, reverse_format_matched_text, reverse_format_score
    
    # Check for full string matches
    if source_norm in target_norm:
        # Calculate base score and apply 50% boost (capped at 90%)
        base_score = (len(source_norm.split()) / len(target_norm.split())) * 100
        boosted_score = min(90.0, base_score * 1.5)  # 50% boost, capped at 90%
        return True, "source_in_target", source_norm, boosted_score
    if target_norm in source_norm:
        # Calculate base score and apply 50% boost (capped at 90%)
        base_score = (len(target_norm.split()) / len(source_norm.split())) * 100
        boosted_score = min(90.0, base_score * 1.5)  # 50% boost, capped at 90%
        return True, "target_in_source", target_norm, boosted_score
    
    # Check for word combination matches
    source_combinations = get_word_combinations(source_norm, min_words)
    target_combinations = get_word_combinations(target_norm, min_words)
    
    # Check if any source combination appears in target
    for combo in source_combinations:
        if combo in target_norm:
            # Calculate similarity score based on how much of the strings match
            score = (len(combo.split()) / max(len(source_norm.split()), len(target_norm.split()))) * 100
            return True, "source_combo_in_target", combo, score
    
    # Check if any target combination appears in source
    for combo in target_combinations:
        if combo in source_norm:
            # Calculate similarity score based on how much of the strings match
            score = (len(combo.split()) / max(len(source_norm.split()), len(target_norm.split()))) * 100
            return True, "target_combo_in_source", combo, score
    
    return False, "no_match", "", 0.0

def compare_single_source_line(args):
    """Compare a single source line against all target lines for substring matches."""
    source_idx, source_line, target_data, min_words = args
    matches = []
    
    # Pre-filter by minimum length
    source_words = len(source_line.split())
    if source_words < 3:  # Skip very short sources
        return None
    
    # Pre-filter target data to avoid checking every line
    filtered_targets = []
    for target_idx, target_line in enumerate(target_data):
        target_words = len(target_line.split())
        if target_words >= 3:  # Only consider targets with 3+ words
            filtered_targets.append((target_idx, target_line))
    
    # Early exit if no valid targets
    if not filtered_targets:
        return None
    
    # For very large target datasets, we can optimize by doing quick checks first
    source_norm = normalize_text(source_line)
    
    for target_idx, target_line in filtered_targets:
        # Quick length check - if target is much shorter than source, 
        # it's unlikely to have meaningful matches unless it's a substring
        target_norm = normalize_text(target_line)
        
        # Skip if both strings are very different in length and neither contains the other
        len_ratio = min(len(source_norm), len(target_norm)) / max(len(source_norm), len(target_norm))
        if len_ratio < 0.2:  # If one is less than 20% the length of the other
            # Only check if the shorter one might be contained in the longer one
            if len(source_norm) > len(target_norm):
                if target_norm not in source_norm:
                    continue
            else:
                if source_norm not in target_norm:
                    continue
        
        # Check for substring matches
        is_match, match_type, matched_text, score = is_substring_match(source_line, target_line, min_words)
        
        if is_match:
            matches.append({
                "target_index": target_idx,
                "similarity_score": score,
                "target_line": target_line,
                "match_type": match_type,
                "matched_text": matched_text
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


def compare_json_lines_parallel(source_data, target_data, min_words=4, max_workers=None):
    """Parallel version of substring comparison using multiprocessing."""
    # For very large datasets, limit workers to avoid memory issues
    if len(target_data) > 100000:
        max_workers = min(2, multiprocessing.cpu_count())  # Use only 2 workers for huge datasets
    elif max_workers is None:
        max_workers = min(multiprocessing.cpu_count(), len(source_data), 4)  # Cap at 4 to avoid memory issues
    
    print(f"Processing {len(source_data)} source lines against {len(target_data)} target lines...")
    print(f"Using {max_workers} parallel workers...")
    print(f"Minimum word combination length: {min_words}")
    
    # Pre-filter source data
    filtered_source = [(i, line) for i, line in enumerate(source_data) if len(line.split()) >= 3]
    
    if len(filtered_source) == 0:
        print("No source lines with 3+ words found.")
        return []
    
    # For very large target data, we need to be more memory efficient
    # Split source data into smaller batches to avoid memory issues
    if len(target_data) > 100000:
        batch_size = 1  # Process one source at a time for huge datasets
    else:
        batch_size = max(1, len(filtered_source) // max_workers)
        if len(target_data) > 10000:  # If target is large, use smaller batches
            batch_size = min(batch_size, 10)
    
    matched_lines = []
    
    # Process in batches to avoid memory issues
    for batch_start in range(0, len(filtered_source), batch_size):
        batch_end = min(batch_start + batch_size, len(filtered_source))
        batch_source = filtered_source[batch_start:batch_end]
        
        print(f"Processing batch {batch_start//batch_size + 1}/{(len(filtered_source) + batch_size - 1)//batch_size} ({len(batch_source)} sources)")
        
        # Prepare arguments for this batch
        args_list = [(i, source_line, target_data, min_words) 
                     for i, source_line in batch_source]
        
        with ProcessPoolExecutor(max_workers=min(max_workers, len(args_list))) as executor:
            # Submit all tasks for this batch
            futures = [executor.submit(compare_single_source_line, args) for args in args_list]
            
            # Collect results with progress bar
            completed = 0
            timeout_seconds = 60 if len(target_data) > 100000 else 30  # Longer timeout for huge datasets
            for future in futures:
                try:
                    result = future.result(timeout=timeout_seconds)
                    if result:  # Only add if there were matches
                        matched_lines.append(result)
                    completed += 1
                    if completed % 1 == 0:  # Show progress for each completion
                        print(f"  Completed {completed}/{len(futures)} comparisons in this batch")
                except Exception as e:
                    print(f"  Warning: Task failed with error: {e}")
                    completed += 1
    
    # Sort by source index to maintain order
    matched_lines.sort(key=lambda x: x["source_index"])
    return matched_lines


def compare_json_lines_optimized(source_data, target_data, min_words=4):
    """Optimized single-threaded version for substring matching."""
    matched_lines = []
    print(f"Processing {len(source_data)} source lines against {len(target_data)} target lines...")
    print(f"Minimum word combination length: {min_words}")
    
    # Pre-filter very short strings
    filtered_target = [(i, line) for i, line in enumerate(target_data) if len(line.split()) >= 3]
    
    for i, source_line in enumerate(tqdm(source_data, desc="Comparing lines", unit="line")):
        if len(source_line.split()) < 3:
            continue
            
        target_matches = []
        
        for j, target_line in filtered_target:
            # Check for substring matches
            is_match, match_type, matched_text, score = is_substring_match(source_line, target_line, min_words)
            
            if is_match:
                target_matches.append({
                    "target_index": j,
                    "similarity_score": score,
                    "target_line": target_line,
                    "match_type": match_type,
                    "matched_text": matched_text
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


def compare_json_lines_ultra_fast(source_data, target_data, min_words=4, batch_size=1000):
    """Ultra-fast version with advanced optimizations for substring matching."""
    matched_lines = []
    print(f"Processing {len(source_data)} source lines against {len(target_data)} target lines...")
    print("Using ultra-fast algorithm with advanced optimizations...")
    print(f"Minimum word combination length: {min_words}")
    
    # Pre-filter and create lookup structures
    filtered_source = [(i, line) for i, line in enumerate(source_data) if len(line.split()) >= 3]
    filtered_target = [(i, line) for i, line in enumerate(target_data) if len(line.split()) >= 3]
    
    # For very large datasets, avoid building the full lookup table
    if len(filtered_target) > 50000:
        print("Large dataset detected - using memory-efficient algorithm...")
        # Process without pre-building lookup table to save memory
        for source_idx, source_line in tqdm(filtered_source, desc="Comparing lines", unit="line"):
            source_norm = normalize_text(source_line)
            target_matches = []
            
            # Process targets in chunks to avoid memory issues
            chunk_size = 10000
            for chunk_start in range(0, len(filtered_target), chunk_size):
                chunk_end = min(chunk_start + chunk_size, len(filtered_target))
                target_chunk = filtered_target[chunk_start:chunk_end]
                
                for target_idx, target_line in target_chunk:
                    target_norm = normalize_text(target_line)
                    
                    # Quick length check for optimization
                    len_ratio = min(len(source_norm), len(target_norm)) / max(len(source_norm), len(target_norm))
                    if len_ratio < 0.1 and source_norm not in target_norm and target_norm not in source_norm:
                        continue
                    
                    # Check format specifier matches first
                    is_format_match, format_match_type, format_matched_text, format_score = is_format_specifier_match(source_line, target_line)
                    if is_format_match:
                        target_matches.append({
                            "target_index": target_idx,
                            "similarity_score": format_score,
                            "target_line": target_line,
                            "match_type": format_match_type,
                            "matched_text": format_matched_text
                        })
                        continue
                    
                    # Check reverse format specifier matches
                    is_reverse_format_match, reverse_format_match_type, reverse_format_matched_text, reverse_format_score = is_format_specifier_match(target_line, source_line)
                    if is_reverse_format_match:
                        target_matches.append({
                            "target_index": target_idx,
                            "similarity_score": reverse_format_score,
                            "target_line": target_line,
                            "match_type": "reverse_" + reverse_format_match_type,
                            "matched_text": reverse_format_matched_text
                        })
                        continue
                    
                    # Check exact matches
                    if source_norm == target_norm:
                        target_matches.append({
                            "target_index": target_idx,
                            "similarity_score": 100.0,
                            "target_line": target_line,
                            "match_type": "exact_match",
                            "matched_text": source_norm
                        })
                        continue
                    
                    # Check substring matches
                    if source_norm in target_norm:
                        # Calculate base score and apply 50% boost (capped at 90%)
                        base_score = (len(source_norm.split()) / len(target_norm.split())) * 100
                        score = min(90.0, base_score * 1.5)  # 50% boost, capped at 90%
                        target_matches.append({
                            "target_index": target_idx,
                            "similarity_score": score,
                            "target_line": target_line,
                            "match_type": "source_in_target",
                            "matched_text": source_norm
                        })
                    elif target_norm in source_norm:
                        # Calculate base score and apply 50% boost (capped at 90%)
                        base_score = (len(target_norm.split()) / len(source_norm.split())) * 100
                        score = min(90.0, base_score * 1.5)  # 50% boost, capped at 90%
                        target_matches.append({
                            "target_index": target_idx,
                            "similarity_score": score,
                            "target_line": target_line,
                            "match_type": "target_in_source",
                            "matched_text": target_norm
                        })
                    else:
                        # Check word combinations only if no full string matches
                        source_combinations = get_word_combinations(source_norm, min_words)
                        for combo in source_combinations:
                            if combo in target_norm:
                                score = (len(combo.split()) / max(len(source_norm.split()), len(target_norm.split()))) * 100
                                # Avoid duplicates
                                if not any(match["target_index"] == target_idx for match in target_matches):
                                    target_matches.append({
                                        "target_index": target_idx,
                                        "similarity_score": score,
                                        "target_line": target_line,
                                        "match_type": "source_combo_in_target",
                                        "matched_text": combo
                                    })
                                break  # Only take the first match to avoid duplicates
            
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
    
    # Original ultra-fast algorithm for smaller datasets
    # Create normalized target lookup for faster searching
    target_lookup = {}
    print("Building target lookup table...")
    for idx, line in tqdm(filtered_target, desc="Indexing targets"):
        normalized = normalize_text(line)
        target_lookup[normalized] = (idx, line)
        
        # Also index word combinations (but limit to avoid memory issues)
        combinations = get_word_combinations(normalized, min_words)
        for combo in combinations[:50]:  # Limit combinations to prevent memory explosion
            if combo not in target_lookup:
                target_lookup[combo] = (idx, line)
    
    print("Processing source lines...")
    for source_idx, source_line in tqdm(filtered_source, desc="Comparing lines", unit="line"):
        source_norm = normalize_text(source_line)
        target_matches = []
        
        # Check for format specifier matches first
        for target_idx, target_line in filtered_target:
            # Check format specifier matches
            is_format_match, format_match_type, format_matched_text, format_score = is_format_specifier_match(source_line, target_line)
            if is_format_match:
                target_matches.append({
                    "target_index": target_idx,
                    "similarity_score": format_score,
                    "target_line": target_line,
                    "match_type": format_match_type,
                    "matched_text": format_matched_text
                })
                continue
            
            # Check reverse format specifier matches
            is_reverse_format_match, reverse_format_match_type, reverse_format_matched_text, reverse_format_score = is_format_specifier_match(target_line, source_line)
            if is_reverse_format_match:
                target_matches.append({
                    "target_index": target_idx,
                    "similarity_score": reverse_format_score,
                    "target_line": target_line,
                    "match_type": "reverse_" + reverse_format_match_type,
                    "matched_text": reverse_format_matched_text
                })
        
        # If we already have format specifier matches, skip other checks to avoid duplicates
        if target_matches:
            # Sort matches by similarity score (highest first)
            target_matches.sort(key=lambda x: x["similarity_score"], reverse=True)
            matched_lines.append({
                "source_index": source_idx,
                "source_line": source_line,
                "target_matches": target_matches,
                "match_count": len(target_matches)
            })
            continue
        
        # Quick exact match check
        if source_norm in target_lookup:
            idx, target_line = target_lookup[source_norm]
            target_matches.append({
                "target_index": idx,
                "similarity_score": 100.0,
                "target_line": target_line,
                "match_type": "exact_match",
                "matched_text": source_norm
            })
        
        # Check source combinations against targets
        source_combinations = get_word_combinations(source_norm, min_words)
        for combo in source_combinations:
            if combo in target_lookup:
                idx, target_line = target_lookup[combo]
                score = (len(combo.split()) / max(len(source_norm.split()), len(normalize_text(target_line).split()))) * 100
                
                # Avoid duplicates
                if not any(match["target_index"] == idx for match in target_matches):
                    target_matches.append({
                        "target_index": idx,
                        "similarity_score": score,
                        "target_line": target_line,
                        "match_type": "source_combo_in_target",
                        "matched_text": combo
                    })
        
        # Check if any target appears in source (limited search for memory efficiency)
        for target_idx, target_line in filtered_target[:10000]:  # Limit search to first 10k
            target_norm = normalize_text(target_line)
            if target_norm in source_norm:
                # Avoid duplicates
                if not any(match["target_index"] == target_idx for match in target_matches):
                    # Calculate base score and apply 50% boost (capped at 90%)
                    base_score = (len(target_norm.split()) / len(source_norm.split())) * 100
                    score = min(90.0, base_score * 1.5)  # 50% boost, capped at 90%
                    target_matches.append({
                        "target_index": target_idx,
                        "similarity_score": score,
                        "target_line": target_line,
                        "match_type": "target_in_source",
                        "matched_text": target_norm
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
    parser = argparse.ArgumentParser(description="Match lines between two JSONL files using substring matching.")
    parser.add_argument("source", help="Path to the source JSON lines file.")
    parser.add_argument("target", help="Path to the target JSON lines file.")
    parser.add_argument("--min-words", type=int, default=4, help="Minimum number of consecutive words for combination matching (default=4).")
    parser.add_argument("--min-score", type=float, default=0.0, help="Minimum similarity score to include in results (default=0.0).")
    parser.add_argument("--parallel", action="store_true", help="Use parallel processing for faster comparison.")
    parser.add_argument("--ultra-fast", action="store_true", help="Use ultra-fast algorithm with advanced optimizations.")
    parser.add_argument("--workers", type=int, default=None, help="Number of parallel workers (default: auto).")
    parser.add_argument("--output", "-o", help="Output JSON file to write matches (default: print to console).")
    parser.add_argument("--pretty", action="store_true", help="Pretty print JSON output with indentation.")

    args = parser.parse_args()

    source_data = load_json_lines(args.source)
    target_data = load_json_lines(args.target)
    
    # Warn about large datasets
    if len(target_data) > 100000:
        print(f"⚠️  Warning: Large target dataset detected ({len(target_data)} lines)")
        if args.parallel:
            print("   Parallel processing may be slow with very large datasets.")
            print("   Consider using --ultra-fast for better performance.")
        print()

    if args.ultra_fast:
        matches = compare_json_lines_ultra_fast(source_data, target_data, args.min_words)
    elif args.parallel:
        matches = compare_json_lines_parallel(source_data, target_data, args.min_words, args.workers)
    else:
        matches = compare_json_lines_optimized(source_data, target_data, args.min_words)
    
    # Filter matches by minimum similarity score
    if args.min_score > 0.0:
        original_count = len(matches)
        filtered_matches = []
        total_filtered_targets = 0
        
        for match in matches:
            # Filter target matches by score
            filtered_target_matches = [
                target_match for target_match in match["target_matches"] 
                if target_match["similarity_score"] >= args.min_score
            ]
            
            # Only include source match if it has qualifying target matches
            if filtered_target_matches:
                filtered_match = match.copy()
                filtered_match["target_matches"] = filtered_target_matches
                filtered_match["match_count"] = len(filtered_target_matches)
                filtered_matches.append(filtered_match)
                total_filtered_targets += len(filtered_target_matches)
        
        matches = filtered_matches
        print(f"Filtered {original_count - len(matches)} source matches below score threshold {args.min_score}")
    
    print(f"\nFound substring matches for {len(matches)} source lines (min words: {args.min_words}", end="")
    if args.min_score > 0.0:
        print(f", min score: {args.min_score})", end="")
    else:
        print(")", end="")
    print()  # New line
    
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
