# Tests

This directory contains test suites for the Similarity Checker v3 tools.

## test_extract_strings_from_cplusplus.py

Automated test suite for `extract_strings_from_cplusplus.py`.

### How it works

1. **Auto-discovery**: Scans `testData/cplusplus/` for `.c` and `.h` files
2. **Expected outputs**: Looks for corresponding `*_output.json` files containing expected results
3. **Execution**: Runs `extract_strings_from_cplusplus.py` on each test file
4. **Comparison**: Compares actual output with expected output
5. **Reporting**: Shows detailed pass/fail results

### Usage

```bash
# Run all tests
python3 tests/test_extract_strings_from_cplusplus.py

# Run with verbose output (shows detailed comparisons)
python3 tests/test_extract_strings_from_cplusplus.py -v

# Run using unittest framework
python3 tests/test_extract_strings_from_cplusplus.py --unittest
```

### Adding new test cases

To add a new test case:

1. Add your C/C++ test file to `testData/cplusplus/`
   - Example: `testData/cplusplus/mytest.c`

2. Run the extractor to generate expected output:
   ```bash
   python3 extract_strings_from_cplusplus.py testData/cplusplus/mytest.c > testData/cplusplus/mytest_output.json
   ```

3. Review and edit the expected output file if needed

4. Run the test suite to verify:
   ```bash
   python3 tests/test_extract_strings_from_cplusplus.py
   ```

### Test output format

The test suite provides detailed feedback:

- ✅ **PASS**: When actual output matches expected output
- ❌ **FAIL**: When there's a mismatch, with detailed comparison showing:
  - Missing strings (expected but not found)
  - Extra strings (found but not expected)
  - Side-by-side comparison of expected vs actual

### Example test files

- `testInsertionOperator.c` / `testInsertionOperator_output.json` - Basic stream operator extraction

The test suite automatically discovers all test files, so you can add as many as needed without modifying the test code.
