# Similarity Checker

A comprehensive tool for extracting and analyzing string literals and comments from source code files to create baselines for similarity checking and coverage analysis.

## Overview

This project provides tools to:
- Extract string literals and comments from various programming languages
- Combine multi-line string literals in function calls (e.g., `errmsg()`, `errdetail_log()`)
- Generate baseline JSON files for comparison and analysis
- Test and validate extraction functionality

## Key Features

- **Multi-language support**: C, C++, Python, JavaScript, TypeScript, Java, Go, Rust, Ruby
- **Smart string combination**: Automatically combines multiple string literals within function calls
- **Baseline generation**: Creates JSON baselines with cleaned, deduplicated strings
- **Testing framework**: Comprehensive test suite to prevent regressions

## Project Structure

```
├── generate_baseline.py           # Main script for extracting strings from code
├── compare_json_similarity_fast.py # Fast similarity comparison tool
├── documentdb_baseline.json       # Main baseline file
├── testData/                      # Test data directory
│   ├── README.md                  # Documentation for test data
│   ├── testFunction.c             # Test file with single errmsg string
│   ├── testFunction_output.json   # Expected output for testFunction.c
│   ├── testMultiLineErrMsg.c      # Test file with multi-line errmsg strings  
│   └── testMultiLineErrMsg_output.json # Expected output for testMultiLineErrMsg.c
└── tests/                         # Testing scripts directory
    ├── README.md                  # Documentation for testing framework
    └── test_generate_baseline.py  # Testing framework for generate_baseline.py
```

## Quick Start

### Basic Usage

1. **Extract strings from a single file:**
   ```bash
   python3 generate_baseline.py path/to/file.c output.json
   ```

2. **Extract strings from a directory:**
   ```bash
   python3 generate_baseline.py path/to/directory output.json
   ```

3. **Extract with verbose output:**
   ```bash
   python3 generate_baseline.py path/to/code output.json --verbose
   ```

### Running Tests

**From project root (recommended):**
```bash
# Run all tests
python3 tests/test_generate_baseline.py

# Run with detailed output
python3 tests/test_generate_baseline.py --verbose

# Run specific test
python3 tests/test_generate_baseline.py --test testFunction

# Update expected outputs after changes
python3 tests/test_generate_baseline.py --update
```

**From tests directory:**
```bash
cd tests

# Run all tests
python3 test_generate_baseline.py

# Run with verbose output
python3 test_generate_baseline.py --verbose
```

## Main Scripts

### `generate_baseline.py`
The primary script for extracting strings and comments from source code.

**Features:**
- Extracts string literals and comments from multiple programming languages
- Combines multiple string literals within `errmsg()` and `errdetail_log()` function calls
- Filters out individual strings that are part of combined function calls
- Outputs clean, deduplicated JSON baseline files

**Example:**
```bash
# Extract from a C file with verbose output
python3 generate_baseline.py src/file.c baseline.json --verbose

# Extract from entire repository
python3 generate_baseline.py /path/to/repo repo_baseline.json
```

### `compare_json_similarity_fast.py`
Fast similarity comparison tool for analyzing JSON baselines.

## Testing

The project includes a comprehensive testing framework to ensure reliability and prevent regressions.

### Test Structure
- **Test data**: Located in `testData/` directory
- **Test scripts**: Located in `tests/` directory
- **Expected outputs**: JSON files with `_output.json` suffix

### Adding New Tests

1. **Create test file** in `testData/` directory:
   ```bash
   # Example: testData/myNewTest.c
   ```

2. **Generate expected output**:
   ```bash
   python3 tests/test_generate_baseline.py --update --test myNewTest
   ```

3. **Review and verify** the generated `testData/myNewTest_output.json`

4. **Run the test**:
   ```bash
   python3 tests/test_generate_baseline.py --test myNewTest
   ```

### Development Workflow

1. **Make changes** to `generate_baseline.py`
2. **Run tests** to check for regressions:
   ```bash
   python3 tests/test_generate_baseline.py
   ```
3. **If tests fail**:
   - Fix the regression, OR
   - If change is intentional, update expected outputs:
     ```bash
     python3 tests/test_generate_baseline.py --update
     ```

## Supported File Types

- **C/C++**: `.c`, `.h`, `.cpp`
- **Python**: `.py`
- **JavaScript**: `.js`
- **TypeScript**: `.ts`
- **Java**: `.java`
- **Go**: `.go`
- **Rust**: `.rs`
- **Ruby**: `.rb`

## Requirements

- Python 3.6+
- Standard library modules (no external dependencies)

## Output Format

Generated baseline files are JSON arrays containing cleaned string literals:

```json
[
  "Pre-checks the $changeStream pipeline stages to ensure that only supported stages are added",
  "Stage %s is not permitted in a $changeStream pipeline",
  "PlanExecutor error during aggregation :: caused by :: Invalid range: Expected the sortBy field to be a Date, but it was %s"
]
```

## Contributing

1. Add test cases for new features in `testData/`
2. Run the test suite before submitting changes
3. Update expected outputs if behavior changes are intentional
4. Follow the existing code style and patterns