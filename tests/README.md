# Tests Directory

This directory contains testing scripts for the similaritychecker project.

## Files

- `test_generate_baseline.py` - Testing framework for the `generate_baseline.py` script

## Running Tests

From the project root directory:

```bash
# Run all tests
python3 tests/test_generate_baseline.py

# Run with verbose output
python3 tests/test_generate_baseline.py --verbose

# Run specific test
python3 tests/test_generate_baseline.py --test testMultiLine

# Update expected outputs
python3 tests/test_generate_baseline.py --update
```

Or from within the tests directory:

```bash
cd tests

# Run all tests
python3 test_generate_baseline.py

# Run with verbose output  
python3 test_generate_baseline.py --verbose
```

## Test Data

Test data files are located in the `testData/` directory (one level up from here).

## Adding New Tests

1. Add test file to `testData/` directory
2. Run with `--update` to generate expected output
3. Verify the expected output is correct
4. Run tests to confirm everything works
