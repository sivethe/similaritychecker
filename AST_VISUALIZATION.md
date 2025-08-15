# AST Visualization for Tree-sitter C++ Parser

This project now includes comprehensive AST (Abstract Syntax Tree) visualization capabilities for C++ code using tree-sitter. You can visualize parse trees in multiple formats to better understand code structure and debug parsing issues.

## Features

- **Console output**: Pretty-printed tree structure in terminal
- **JSON format**: Structured data for programmatic analysis
- **Text files**: Save tree structure to text files
- **Graphical output**: PNG, SVG, PDF formats (requires graphviz)
- **Configurable depth**: Control how deep to traverse the tree
- **Color-coded nodes**: Different node types have different colors in graphical output

## Installation

### Basic requirements (already installed):
```bash
pip install tree-sitter tree-sitter-cpp
```

### For graphical output (optional):
```bash
pip install graphviz
```

Note: You may also need to install the Graphviz system package:
- Ubuntu/Debian: `sudo apt install graphviz`
- macOS: `brew install graphviz`
- Windows: Download from https://graphviz.org/download/

## Usage

### Using the main tree-sitter extractor

Generate AST visualization along with string extraction:

```bash
# Print AST to console (depth 6)
python3 generate_baseline_treesitter.py file.cpp output.json --ast-console --ast-depth 6

# Save AST as PNG image
python3 generate_baseline_treesitter.py file.cpp output.json --ast --ast-format png --ast-depth 4

# Save AST as JSON
python3 generate_baseline_treesitter.py file.cpp output.json --ast --ast-format json --ast-output my_ast

# Save AST as text file
python3 generate_baseline_treesitter.py file.cpp output.json --ast --ast-format txt --ast-output my_ast
```

### Using the standalone visualizer

For just AST visualization without string extraction:

```bash
# Print to console
python3 ast_visualizer_standalone.py file.cpp --console --depth 5

# Save as PNG
python3 ast_visualizer_standalone.py file.cpp -o ast_output --format png --depth 4

# Save as SVG with custom title
python3 ast_visualizer_standalone.py file.cpp -o ast_output --format svg --title "My Code AST"

# Save as JSON
python3 ast_visualizer_standalone.py file.cpp -o ast_output --format json --depth 10
```

## Command Line Options

### Main extractor options:
- `--ast`: Generate AST visualization
- `--ast-console`: Print AST to console instead of file
- `--ast-format {png,svg,pdf,txt,json}`: Output format (default: png)
- `--ast-depth N`: Maximum tree depth (default: 8)
- `--ast-output PATH`: Output file path without extension

### Standalone visualizer options:
- `-o, --output PATH`: Output file path without extension
- `-f, --format {png,svg,pdf,txt,json}`: Output format (default: png)
- `-d, --depth N`: Maximum tree depth (default: 8)
- `--console`: Print to console instead of saving
- `--title TEXT`: Custom title for visualization

## Examples

### Example 1: Debug StringBuilder operations
```bash
python3 generate_baseline_treesitter.py testData/generate_baseline/testStringBuilder.c output.json --ast-console --ast-depth 6
```

This shows the full AST structure to understand how StringBuilder operations are parsed and why certain patterns might not be detected correctly.

### Example 2: Generate code documentation
```bash
python3 ast_visualizer_standalone.py src/main.cpp -o docs/main_ast --format svg --depth 5 --title "Main Function AST"
```

Creates an SVG diagram showing the structure of your main function for documentation purposes.

### Example 3: Analyze complex expressions
```bash
python3 ast_visualizer_standalone.py complex_code.cpp -o analysis --format json --depth 10
```

Generates detailed JSON data that can be processed programmatically to analyze code complexity, nesting levels, or other metrics.

## Output Formats

### Console Output
- Tree structure with Unicode box-drawing characters
- Truncated text content for readability
- Configurable depth limit

### JSON Format
- Complete structured representation
- Includes node types, positions, and text content
- Suitable for programmatic analysis
- Contains start/end points and byte offsets

### Text Format
- Same as console output but saved to file
- Good for documentation or sharing

### Graphical Formats (PNG, SVG, PDF)
- Color-coded nodes by type
- Hierarchical layout
- Clean, professional appearance
- Suitable for presentations or documentation

## Node Color Coding (Graphical Output)

- **Function definitions**: Light green
- **Control flow** (if, for, while): Light cyan/coral
- **Expressions**: Light steel blue
- **String literals**: Light golden yellow
- **Comments**: Light sea green
- **Declarations**: Light violet
- **Identifiers**: White
- **Other nodes**: Light blue

## Tips

1. **Start with low depth**: Use `--depth 3` or `--depth 4` first to get an overview
2. **Use console output for quick debugging**: `--ast-console` is fastest for immediate feedback
3. **JSON for analysis**: Use JSON format when you need to process the AST programmatically
4. **PNG for sharing**: PNG format works best for sharing or embedding in documents
5. **SVG for web**: SVG format is ideal for web documentation or interactive displays

## Troubleshooting

### "graphviz package not available"
Install graphviz: `pip install graphviz` and ensure the system package is installed.

### Tree too large/complex
- Reduce `--depth` parameter (try 3-5)
- Focus on specific functions rather than entire files
- Use text format instead of graphical for very large trees

### JSON file too large
- Reduce depth limit
- Consider processing smaller code files
- Use streaming JSON processing if analyzing programmatically

## Integration with Development Workflow

The AST visualization can be integrated into your development workflow:

1. **Code Review**: Generate AST diagrams to understand complex code changes
2. **Documentation**: Include AST diagrams in technical documentation
3. **Debugging**: Use console output to understand parsing issues
4. **Education**: Visualize AST to teach code structure concepts
5. **Analysis**: Use JSON output for automated code quality analysis
