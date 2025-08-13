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
    
    # Special case: if both source and target have format specifiers,
    # compare them by converting format specifiers to a common pattern
    if has_format_specifiers(target):
        # Convert both to normalized patterns for comparison
        source_pattern = re.sub(r'%[-#+ 0]*\*?(?:\d+|\*)?(?:\.(?:\d+|\*))?[hlL]?[diouxXeEfFgGaAcspn%]', '%FORMAT%', source_norm)
        target_pattern = re.sub(r'%[-#+ 0]*\*?(?:\d+|\*)?(?:\.(?:\d+|\*))?[hlL]?[diouxXeEfFgGaAcspn%]', '%FORMAT%', target_norm)
        
        if source_pattern == target_pattern:
            # Calculate similarity based on how many format specifiers match the same positions
            source_specs = re.findall(r'%[-#+ 0]*\*?(?:\d+|\*)?(?:\.(?:\d+|\*))?[hlL]?[diouxXeEfFgGaAcspn%]', source_norm)
            target_specs = re.findall(r'%[-#+ 0]*\*?(?:\d+|\*)?(?:\.(?:\d+|\*))?[hlL]?[diouxXeEfFgGaAcspn%]', target_norm)
            
            if len(source_specs) == len(target_specs):
                # High score for same structure, even with different format specifier types
                score = 85.0
                return True, "format_specifier_match", source_norm, score
    
    # Original logic: source has format specifiers, target has actual values
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

def get_word_combinations_limited(text, min_words=4, max_combinations=10):
    """Get limited word combinations for performance optimization."""
    words = text.split()
    combinations = []
    
    # Prioritize longer combinations first for better matches
    for length in range(min(len(words), min_words + 5), min_words - 1, -1):
        for start in range(len(words) - length + 1):
            if len(combinations) >= max_combinations:
                return combinations
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
        return True, "source_in_target", source_norm, 100.0
    if target_norm in source_norm:
        return True, "target_in_source", target_norm, 100.0
    
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
    
    # Pre-filter and pre-normalize all data once
    print("Pre-processing and filtering data...")
    filtered_source = []
    for i, line in enumerate(source_data):
        words = line.split()
        if len(words) >= 3:
            norm = normalize_text(line)
            filtered_source.append((i, line, norm, words))
    
    filtered_target = []
    for i, line in enumerate(target_data):
        words = line.split()
        if len(words) >= 3:
            norm = normalize_text(line)
            filtered_target.append((i, line, norm, words))
    
    print(f"After filtering: {len(filtered_source)} source, {len(filtered_target)} target lines")
    
    # Build efficient lookup structures
    print("Building optimized lookup structures...")
    
    # For exact matches - simple dict
    exact_lookup = {}
    # For substring matches - dict of normalized text to list of targets
    target_by_norm = {}
    # For word combinations - dict of combinations to targets (limited)
    combo_lookup = {}
    
    for target_idx, target_line, target_norm, target_words in filtered_target:
        # Exact match lookup
        if target_norm not in exact_lookup:
            exact_lookup[target_norm] = []
        exact_lookup[target_norm].append((target_idx, target_line))
        
        # Substring lookup
        target_by_norm[target_norm] = (target_idx, target_line, len(target_words))
        
        # Limited word combinations for performance
        if len(target_words) <= 20:  # Only for reasonable length strings
            combinations = get_word_combinations_limited(target_norm, min_words, max_combinations=10)
            for combo in combinations:
                if combo not in combo_lookup:
                    combo_lookup[combo] = []
                if len(combo_lookup[combo]) < 5:  # Limit to prevent memory explosion
                    combo_lookup[combo].append((target_idx, target_line, len(combo.split())))
    
    # For very large datasets, use streaming approach
    # For very large datasets, use streaming approach
    if len(filtered_target) > 50000:
        print("Large dataset detected - using memory-efficient streaming algorithm...")
        return process_large_dataset_optimized(filtered_source, filtered_target, min_words)
    
    # Process source lines with optimized lookups
    print("Processing source lines with optimized lookups...")
    for source_idx, source_line, source_norm, source_words in tqdm(filtered_source, desc="Comparing lines", unit="line"):
        target_matches = []
        
        # 1. Quick exact match check (O(1))
        if source_norm in exact_lookup:
            for target_idx, target_line in exact_lookup[source_norm]:
                target_matches.append({
                    "target_index": target_idx,
                    "similarity_score": 100.0,
                    "target_line": target_line,
                    "match_type": "exact_match",
                    "matched_text": source_norm
                })
        
        # 2. Fast substring matching - check if source is contained in any target
        for target_norm, (target_idx, target_line, target_word_count) in target_by_norm.items():
            if source_norm in target_norm and source_norm != target_norm:
                score = (len(source_words) / target_word_count) * 100
                target_matches.append({
                    "target_index": target_idx,
                    "similarity_score": score,
                    "target_line": target_line,
                    "match_type": "source_in_target",
                    "matched_text": source_norm
                })
            elif target_norm in source_norm and source_norm != target_norm:
                score = (target_word_count / len(source_words)) * 100
                target_matches.append({
                    "target_index": target_idx,
                    "similarity_score": score,
                    "target_line": target_line,
                    "match_type": "target_in_source",
                    "matched_text": target_norm
                })
        
        # 3. Word combination matching (limited for performance)
        if len(target_matches) < 5:  # Only if we don't have many matches already
            source_combinations = get_word_combinations_limited(source_norm, min_words, max_combinations=5)
            for combo in source_combinations:
                if combo in combo_lookup:
                    for target_idx, target_line, combo_word_count in combo_lookup[combo]:
                        # Avoid duplicates
                        if not any(match["target_index"] == target_idx for match in target_matches):
                            score = (combo_word_count / max(len(source_words), len(target_line.split()))) * 100
                            target_matches.append({
                                "target_index": target_idx,
                                "similarity_score": score,
                                "target_line": target_line,
                                "match_type": "source_combo_in_target",
                                "matched_text": combo
                            })
        
        # 4. Format specifier matching (only for lines with % symbols for efficiency)
        if '%' in source_line and len(target_matches) < 10:
            for target_idx, target_line, target_norm, target_words in filtered_target[:1000]:  # Limit search
                if not any(match["target_index"] == target_idx for match in target_matches):
                    is_format_match, format_match_type, format_matched_text, format_score = is_format_specifier_match(source_line, target_line)
                    if is_format_match:
                        target_matches.append({
                            "target_index": target_idx,
                            "similarity_score": format_score,
                            "target_line": target_line,
                            "match_type": format_match_type,
                            "matched_text": format_matched_text
                        })
        
        # Only add if there were matches
        if target_matches:
            # Sort matches by similarity score (highest first) and limit results
            target_matches.sort(key=lambda x: x["similarity_score"], reverse=True)
            # Limit to top 20 matches to prevent memory issues
            target_matches = target_matches[:20]
            
            matched_lines.append({
                "source_index": source_idx,
                "source_line": source_line,
                "target_matches": target_matches,
                "match_count": len(target_matches)
            })
    
    return matched_lines

def process_large_dataset_optimized(filtered_source, filtered_target, min_words):
    """Optimized processing for very large datasets with memory efficiency."""
    matched_lines = []
    
    # Build minimal lookup structures for large datasets
    target_norms = {}
    target_by_index = {}  # Keep access to original lines for format specifier matching
    
    for target_idx, target_line, target_norm, target_words in filtered_target:
        target_norms[target_norm] = (target_idx, target_line, len(target_words))
        target_by_index[target_idx] = (target_line, target_norm, len(target_words))
    
    # Process in smaller batches
    batch_size = 100
    for batch_start in range(0, len(filtered_source), batch_size):
        batch_end = min(batch_start + batch_size, len(filtered_source))
        source_batch = filtered_source[batch_start:batch_end]
        
        for source_idx, source_line, source_norm, source_words in tqdm(source_batch, desc=f"Batch {batch_start//batch_size + 1}", leave=False):
            target_matches = []
            
            # Fast exact and substring matching only
            for target_norm, (target_idx, target_line, target_word_count) in target_norms.items():
                if source_norm == target_norm:
                    target_matches.append({
                        "target_index": target_idx,
                        "similarity_score": 100.0,
                        "target_line": target_line,
                        "match_type": "exact_match",
                        "matched_text": source_norm
                    })
                elif source_norm in target_norm:
                    score = (len(source_words) / target_word_count) * 100
                    target_matches.append({
                        "target_index": target_idx,
                        "similarity_score": score,
                        "target_line": target_line,
                        "match_type": "source_in_target",
                        "matched_text": source_norm
                    })
                elif target_norm in source_norm:
                    score = (target_word_count / len(source_words)) * 100
                    target_matches.append({
                        "target_index": target_idx,
                        "similarity_score": score,
                        "target_line": target_line,
                        "match_type": "target_in_source",
                        "matched_text": target_norm
                    })
            
            # Add format specifier matching for large datasets (improved sampling)
            if '%' in source_line and len(target_matches) < 5:
                # For large datasets, use better sampling strategy
                # Strategy 1: Sample from beginning, middle, and end sections
                total_targets = len(filtered_target)
                sample_size = min(5000, total_targets)
                
                # Take samples from different sections to ensure coverage
                section_size = total_targets // 3
                samples_per_section = sample_size // 3
                
                sampled_targets = []
                # Beginning section
                step1 = max(1, section_size // samples_per_section)
                sampled_targets.extend(filtered_target[0:section_size:step1])
                
                # Middle section  
                step2 = max(1, section_size // samples_per_section)
                sampled_targets.extend(filtered_target[section_size:2*section_size:step2])
                
                # End section
                step3 = max(1, section_size // samples_per_section)
                sampled_targets.extend(filtered_target[2*section_size::step3])
                
                # Strategy 2: Also include lines with format specifiers for better accuracy
                format_targets = [t for t in filtered_target[:10000] if '%' in t[1]]  # Check first 10k for format specifiers
                sampled_targets.extend(format_targets[:1000])  # Add up to 1000 format specifier lines
                
                # Remove duplicates by target_idx
                seen_indices = set()
                unique_targets = []
                for target_idx, target_line, target_norm, target_words in sampled_targets:
                    if target_idx not in seen_indices:
                        seen_indices.add(target_idx)
                        unique_targets.append((target_idx, target_line, target_norm, target_words))
                
                for target_idx, target_line, target_norm, target_words in unique_targets:
                    if not any(match["target_index"] == target_idx for match in target_matches):
                        is_format_match, format_match_type, format_matched_text, format_score = is_format_specifier_match(source_line, target_line)
                        if is_format_match:
                            target_matches.append({
                                "target_index": target_idx,
                                "similarity_score": format_score,
                                "target_line": target_line,
                                "match_type": format_match_type,
                                "matched_text": format_matched_text
                            })
                            # Only add first format match to keep performance reasonable
                            break
            
            if target_matches:
                target_matches.sort(key=lambda x: x["similarity_score"], reverse=True)
                target_matches = target_matches[:10]  # Limit for large datasets
                
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
