# Tests Directory

This directory contains testing scripts for the similaritychecker project.

## Test Suites

### Master Test Runner
- `run_all_tests.py` - Master test runner that executes all test suites

### Individual Test Suites
- `test_generate_baseline.py` - Testing framework for the `generate_baseline.py` script
- `test_compare_similarity.py` - Testing framework for the `compare_json_similarity_fast.py` script

## Quick Start

### Run All Tests
```bash
# From project root - run all test suites
python3 tests/run_all_tests.py

# Run with verbose output
python3 tests/run_all_tests.py --verbose

# Run only baseline tests
python3 tests/run_all_tests.py --baseline

# Run only similarity tests  
python3 tests/run_all_tests.py --similarity
```

### Individual Test Suites

#### Baseline Generation Tests
```bash
# Run all baseline tests
python3 tests/test_generate_baseline.py

# Run with verbose output
python3 tests/test_generate_baseline.py --verbose

# Run specific test
python3 tests/test_generate_baseline.py --test testMultiLine

# Update expected outputs
python3 tests/test_generate_baseline.py --update
```

#### Similarity Comparison Tests
```bash
# Run all similarity tests
python3 tests/test_compare_similarity.py

# Run with verbose output
python3 tests/test_compare_similarity.py --verbose

# Run with different word minimum
python3 tests/test_compare_similarity.py --min-words 3

# Update expected outputs
python3 tests/test_compare_similarity.py --update
```

## Test Data Structure

Test data files are organized in the `testData/` directory:

```
testData/
├── generate_baseline/          # Test files for baseline generation
│   ├── testFunction.c         # Single string test
│   ├── testFunction_output.json
│   ├── testMultiLineErrMsg.c  # Multi-line string test
│   └── testMultiLineErrMsg_output.json
└── compare_similarity/         # Test files for similarity comparison
    ├── exactMatch/            # Test case: exact string matching
    │   ├── source.json        # Source data
    │   ├── target.json        # Target data
    │   └── expected.json      # Expected results
    └── sourceSubstringMatch/  # Test case: substring matching
        ├── source.json        # Source data
        ├── target.json        # Target data
        └── expected.json      # Expected results
```

## Adding New Tests

### For Baseline Generation (`generate_baseline.py`)
1. Add test file (e.g., `newTest.c`) to `testData/generate_baseline/`
2. Run `python3 tests/test_generate_baseline.py --update` to generate expected output
3. Verify the expected output file (`newTest_output.json`) is correct
4. Run tests to confirm everything works

### For Similarity Comparison (`compare_json_similarity_fast.py`)
1. Create a new test directory under `testData/compare_similarity/`:
   ```bash
   mkdir testData/compare_similarity/myNewTest
   ```
2. Add test files to the new directory:
   - `source.json` - Source data (JSON array of strings)
   - `target.json` - Target data (JSON array of strings)
3. Run `python3 tests/test_compare_similarity.py --update --test myNewTest` to generate expected output
4. Verify the expected output file (`expected.json`) is correct
5. Run tests to confirm everything works

## Test Output Validation

### Baseline Tests
- Validates extracted strings match expected output exactly
- Checks for proper string combination in function calls
- Ensures consistent ordering and deduplication

### Similarity Tests  
- Validates output structure (required fields, data types)
- Checks match types are valid (`source_in_target`, `target_in_source`, etc.)
- Compares match counts and target indices
- Ensures consistent results across different algorithms

## Continuous Integration

The master test runner (`run_all_tests.py`) is designed for CI/CD integration:
- Returns non-zero exit code on test failures
- Provides structured output for easy parsing
- Supports selective test suite execution
- Includes timing and performance validation
