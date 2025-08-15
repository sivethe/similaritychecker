# Similarity Checker v3

A comprehensive toolkit for analyzing C/C++ source code, extracting string patterns from stream operators, visualizing AST trees, and performing similarity comparisons between files. This toolset is designed for code analysis, baseline generation, and similarity matching workflows.

## Overview

This project consists of three main Python tools that work together to provide a complete code analysis pipeline:

1. **`extract_stream_operators.py`** - Core extraction engine for C++ stream operator patterns
2. **`generate_baseline_treesitter.py`** - Batch processor for creating baselines from multiple files
3. **`ast_visualizer_standalone.py`** - AST visualization tool for understanding code structure
4. **`rapidfuzz_file_compare.py`** - High-performance similarity matcher for comparing extracted patterns

## Features

- **Stream Operator Pattern Extraction**: Analyzes C++ `<<` operators and converts them to standardized string patterns
- **AST Visualization**: Generate textual and JSON representations of Abstract Syntax Trees
- **Batch Processing**: Process entire directories of C++ files with filtering and exclusion options
- **Fast Similarity Matching**: Compare files using RapidFuzz for efficient fuzzy string matching
- **Multiple Output Formats**: Support for JSON and text outputs
- **Error Handling**: Robust error handling with detailed reporting and continuation options

## Installation

### Prerequisites

Install the required Python packages:

```bash
# Core dependencies
pip install tree-sitter tree-sitter-cpp rapidfuzz

# For Bloom filter optimization (recommended)
pip install pybloom-live
```

## Tools Reference

### 1. extract_stream_operators.py

**Purpose**: Core extraction engine that parses C++ files using tree-sitter and extracts stream operator (`<<`) patterns.

**Key Features**:
- Converts string literals to their actual content
- Replaces function calls, identifiers, and expressions with `%s` placeholders
- Provides detailed error reporting for unsupported patterns
- Outputs JSON array of extracted patterns

**Usage**:
```bash
# Extract patterns from a single file
python3 extract_stream_operators.py input.cpp

# Save output to file
python3 extract_stream_operators.py input.cpp output.json

# Verbose mode for debugging
python3 extract_stream_operators.py input.cpp --verbose
```

**Example Output**:
```json
[
  "Error: %s",
  "Processing file: %s with %s parameters",
  "Status: %s (code: %s)"
]
```

### 2. generate_baseline_treesitter.py

**Purpose**: Batch processor that wraps `extract_stream_operators.py` to handle multiple files and directories.

**Key Features**:
- Process entire directory trees
- Flexible exclusion patterns (substring and glob matching)
- Error tracking with continue-on-error or fail-fast modes
- Automatic deduplication of extracted patterns
- Progress reporting for large codebases

**Usage**:
```bash
# Process single file
python3 generate_baseline_treesitter.py file.cpp output.json

# Process entire directory
python3 generate_baseline_treesitter.py src/ baseline.json

# Exclude specific patterns
python3 generate_baseline_treesitter.py src/ baseline.json --exclude build --exclude "*/test/*"

# Verbose output with error details
python3 generate_baseline_treesitter.py src/ baseline.json --verbose

# Fail immediately on first error
python3 generate_baseline_treesitter.py src/ baseline.json --fail-on-error
```

**Default Exclusions**: `.git/`, `.svn/`, `node_modules/`, `__pycache__/`, `.vscode/`, `.idea/`, `vendor/`, `third_party/`, `external/`

### 3. ast_visualizer_standalone.py

**Purpose**: Standalone AST visualization tool for understanding code structure and debugging parsing issues.

**Key Features**:
- Multiple output formats: console, JSON, text
- Configurable tree depth limits
- Support for custom titles
- Detailed AST structure analysis

**Usage**:
```bash
# Print AST to console
python3 ast_visualizer_standalone.py file.cpp --console

# Export as JSON for programmatic analysis
python3 ast_visualizer_standalone.py file.cpp -o ast_data --format json

# Save as text file
python3 ast_visualizer_standalone.py file.cpp -o ast_tree --format txt

# Limit tree depth for large files
python3 ast_visualizer_standalone.py file.cpp --console --depth 5
```

**Supported Formats**: `txt`, `json`

### 4. rapidfuzz_file_compare.py

**Purpose**: High-performance similarity matching tool for comparing extracted patterns between files.

**Key Features**:
- Multiple similarity algorithms (ratio, partial ratio, token sort, token set)
- Configurable similarity thresholds
- Support for both JSON arrays and text files
- Automatic timestamped output files
- Detailed match statistics and summaries

**Usage**:
```bash
# Basic comparison with 70% threshold
python3 rapidfuzz_file_compare.py source.json target.json

# Custom threshold and match limits
python3 rapidfuzz_file_compare.py source.json target.json --threshold 80 --max-matches 3

# Compare text files
python3 rapidfuzz_file_compare.py source.txt target.txt --threshold 60
```

**Output Files**:
- `{source}_vs_{target}_matches_{threshold}pct_{timestamp}.json` - Found matches
- `{source}_vs_{target}_unmatched_{threshold}pct_{timestamp}.json` - Unmatched lines

## Workflow Examples

### Basic Code Analysis Workflow

```bash
# 1. Extract patterns from a single file
python3 extract_stream_operators.py main.cpp patterns.json

# 2. Visualize the AST for debugging
python3 ast_visualizer_standalone.py main.cpp --console

# 3. Generate baseline from entire project
python3 generate_baseline_treesitter.py src/ project_baseline.json --verbose

# 4. Compare with another codebase
python3 rapidfuzz_file_compare.py patterns.json project_baseline.json
```

### Large Project Analysis

```bash
# Process large codebase with exclusions
python3 generate_baseline_treesitter.py /path/to/project baseline.json \
    --exclude build --exclude "*/third_party/*" --exclude "*.pb.h" \
    --verbose

# Compare against reference baseline
python3 rapidfuzz_file_compare.py baseline.json reference_baseline.json \
    --threshold 75 --max-matches 10
```

### Debug Parsing Issues

```bash
# Generate detailed AST visualization
python3 ast_visualizer_standalone.py problematic_file.cpp -o debug_ast --format json

# Extract with verbose error reporting
python3 extract_stream_operators.py problematic_file.cpp --verbose

# Check what the baseline generator sees
python3 generate_baseline_treesitter.py problematic_file.cpp debug.json --verbose --fail-on-error
```

## Understanding Output

### Stream Operator Patterns

The tools convert C++ stream expressions like:
```cpp
std::cout << "Error: " << errorCode << " in function " << funcName;
uasserted(123) << "Failed to process " << filename;
```

Into standardized patterns:
```json
[
  "Error: %s in function %s",
  "Failed to process %s"
]
```

### AST Visualization

The AST visualizer helps understand how the parser interprets your code, showing:
- Node types and relationships
- String literals and their positions
- Function calls and expressions
- Syntactic structure

### Similarity Matching

The comparison tool provides multiple similarity metrics:
- **Ratio**: Overall string similarity
- **Partial Ratio**: Best substring match
- **Token Sort**: Similarity after sorting words
- **Token Set**: Set-based token comparison

## Error Handling

All tools include robust error handling:

- **extract_stream_operators.py**: Reports unsupported AST patterns with detailed context
- **generate_baseline_treesitter.py**: Continues processing on errors unless `--fail-on-error` is used
- **ast_visualizer_standalone.py**: Gracefully handles parsing failures and missing dependencies
- **rapidfuzz_file_compare.py**: Validates input files and similarity parameters

## Performance Notes

- **Bloom Filters**: Install `pybloom-live` for memory-efficient duplicate detection in large codebases
- **Batch Processing**: Use directory-level processing rather than individual file calls for better performance
- **Tree Depth**: Limit AST visualization depth for very large files to avoid memory issues
- **Similarity Thresholds**: Higher thresholds (80%+) run faster but may miss valid matches

## File Structure

```
testData/
├── generate_baseline/          # Test files for baseline generation
│   ├── testFunction.c         # Example C function
│   ├── testStringBuilder.c    # String builder patterns
│   └── *.json                 # Expected outputs
├── source.json                # Sample source patterns
├── target.json                # Sample target patterns
└── *_matches_*.json          # Generated comparison results
```
