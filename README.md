# IfcPeek

An interactive command-line shell for querying IFC models.

## Requirements

- Python 3.9+
- IfcOpenShell
- prompt\_toolkit

## Installation

```bash
# Clone the repository
git clone https://github.com/brunopostle/ifcpeek.git
cd ifcpeek

# Install dependencies
pip install ifcopenshell prompt_toolkit

# Install the package
pip install -e .
```

## Usage

### Basic Usage
```bash
# Start IfcPeek with an IFC file
ifcpeek path/to/your/model.ifc

# Or use as a Python module
python -m ifcpeek path/to/your/model.ifc
```

### Interactive Shell
```
> IfcWall                           # Find all walls
> IfcWall, material=concrete        # Find concrete walls
> IfcElement, Name=Door-01          # Find element by name
> IfcWall | IfcDoor                 # Find walls OR doors
> /help                             # Show help information
> /exit                             # Exit the shell
```

### Non-Interactive Usage
```
# Query with STDIN, result to STDOUT
echo IfcWall | ifcpeek path/to/your/model.ifc

ifcpeek path/to/your/model.ifc < queries.txt > results.txt
```

## Commands

| Command | Description |
|---------|-------------|
| `/help` | Show comprehensive help information |
| `/exit` | Exit the shell |
| `/quit` | Exit the shell |
| `Ctrl-D` | Exit the shell |
| `Ctrl-C` | Return to prompt (doesn't crash) |
| `Up/Down` | Navigate command history |
| `Ctrl-R` | Search command history |

```

## Testing

### Run All Tests
```bash
# Run complete test suite
python -m pytest tests/ -v
```

### Test Coverage
```bash
# Install coverage tools
pip install pytest-cov

# Run tests with coverage
python -m pytest tests/ --cov=ifcpeek --cov-report=html
```

## Contributing

### Development Setup
```bash
# Clone repository
git clone https://github.com/brunopostle/ifcpeek.git
cd ifcpeek

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"

# Run tests
python -m pytest tests/ -v
```

### Code Style
- Follow PEP 8 guidelines
- Use type hints where appropriate
- Write comprehensive docstrings
- Include error handling for all functions
- Add debug logging for complex operations

### Testing Requirements
- All new features must include tests
- Error handling paths must be tested
- Integration tests for end-to-end scenarios
- Performance impact assessment

## License

This project is licensed under the GPLv3 License - see the [LICENSE](LICENSE) file for details.

## Support

### Getting Help
- **Documentation**: Check this README and inline help (`/help`)
- **Issues**: Report bugs on GitHub Issues

### Reporting Issues
When reporting issues, please include:
1. **Error message** - Full traceback from error handling
2. **File information** - IFC file size, schema, source
3. **Environment** - Python version, OS, dependencies
4. **Steps to reproduce** - Exact commands and inputs used

### Feature Requests
We welcome suggestions for improvements:
- Error handling capabilities
- Additional debugging features
- Performance optimizations
- User experience improvements

---

**IfcPeek** - IFC model querying.
