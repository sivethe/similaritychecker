# Compare Similarity Tests

This directory contains comprehensive test cases for the `compare_json_similarity_fast.py` script.

## Test Directory Structure

Each test directory follows a consistent pattern:
- `source.json` - Source strings to match
- `target.json` - Target strings to search within  
- `expected.json` - Expected output for validation
- `README.md` - Description of the test scenario

### Test Categories

#### Core Functionality
- **`exactMatch/`** - Tests exact string matching
- **`sourceSubstringMatch/`** - Tests basic substring matching
- **`formatSpecifiers/`** - Tests C printf format specifier matching

#### Boost Scoring (50% boost, capped at 90%)
- **`sourceInTarget_boostScoring/`** - Tests boost scoring with 90% cap
- **`sourceInTarget_boostScoringRange/`** - Tests full range of boost scores
- **`targetInSource_boostScoring/`** - Tests reverse boost scoring

#### Score Filtering
- **`scoreFiltering_25/`** - Tests 25% minimum score threshold
- **`scoreFiltering_50/`** - Tests 50% minimum score threshold

## Running Tests

```bash
# Run all tests
python3 tests/test_compare_similarity.py

# Run specific test category
python3 tests/test_compare_similarity.py --test sourceInTarget

# Run with verbose output
python3 tests/test_compare_similarity.py --verbose
```

## Test Validation

Each test validates:
1. **Structure** - Correct JSON format and required fields
2. **Comparison** - Results match expected output exactly
3. **Match Types** - Correct identification of match types
4. **Scoring** - Proper similarity score calculations
