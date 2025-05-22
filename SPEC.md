# IfcPeek Interactive CLI Tool - Complete Developer Specification

## Project Overview

IfcPeek is an interactive command-line shell for querying IFC (Industry Foundation Classes) models using IfcOpenShell's selector syntax. It provides a Unix shell-like interface for exploring and filtering IFC entities with persistent history and robust error handling.

## Requirements Summary

### Functional Requirements
- Load IFC files via command-line argument
- Interactive shell with selector query support
- SPF format output for matching entities
- Persistent command history with search
- Built-in commands for help and exit
- Full error reporting with Python tracebacks

### Non-Functional Requirements
- Professional Python package structure
- XDG-compliant configuration storage
- Cross-platform compatibility
- Extensible architecture for future features

## Package Configuration

### Project Metadata
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "ifcpeek"
version = "1.0.0"
description = "Interactive command-line shell for querying IFC models"
authors = [{name = "Your Name", email = "your.email@domain.com"}]
license = {text = "MIT"}
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "ifcopenshell>=0.7.0",
    "prompt-toolkit>=3.0.0",
]
keywords = ["ifc", "bim", "ifcopenshell", "shell", "cli"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Scientific/Engineering",
]

[project.scripts]
ifcpeek = "ifcpeek.__main__:main"

[project.urls]
Homepage = "https://github.com/username/ifcpeek"
Repository = "https://github.com/username/ifcpeek"
Issues = "https://github.com/username/ifcpeek/issues"
```

## Project Structure

```
ifcpeek/
├── pyproject.toml
├── README.md
├── LICENSE
├── .gitignore
├── src/
│   └── ifcpeek/
│       ├── __init__.py
│       ├── __main__.py
│       ├── shell.py
│       ├── config.py
│       └── exceptions.py
├── tests/
│   ├── __init__.py
│   ├── test_main.py
│   ├── test_shell.py
│   ├── conftest.py
│   └── fixtures/
│       ├── valid_model.ifc
│       └── invalid_model.txt
└── docs/
    └── README.md
```

## Technical Architecture

### Core Components

#### 1. Main Module (`__main__.py`)
```python
"""Entry point for ifcpeek command."""
import sys
import argparse
from pathlib import Path
from .shell import IfcPeek
from .exceptions import IfcPeekError

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog='ifcpeek',
        description='Interactive shell for querying IFC models'
    )
    parser.add_argument('ifc_file', help='Path to IFC file')
    
    try:
        args = parser.parse_args()
        shell = IfcPeek(args.ifc_file)
        shell.run()
    except IfcPeekError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == '__main__':
    main()
```

#### 2. Shell Class (`shell.py`)
```python
"""Interactive shell implementation."""
import sys
from pathlib import Path
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.shortcuts import print_formatted_text
import ifcopenshell
import ifcopenshell.util.selector
from .config import get_history_file_path
from .exceptions import IfcPeekError

class IfcPeek:
    """Interactive IFC query shell."""
    
    def __init__(self, ifc_file_path: str):
        """Initialize shell with IFC model."""
        self.ifc_file_path = Path(ifc_file_path)
        self.model = self._load_model()
        self.session = self._create_session()
    
    def _load_model(self):
        """Load IFC model with comprehensive error handling."""
        # Implementation details in full code section
        
    def _create_session(self):
        """Create prompt_toolkit session with history."""
        # Implementation details in full code section
        
    def run(self):
        """Main shell loop."""
        # Implementation details in full code section
```

#### 3. Configuration (`config.py`)
```python
"""Configuration and file path management."""
import os
from pathlib import Path

def get_config_dir() -> Path:
    """Get XDG-compliant config directory."""
    if xdg_state := os.environ.get('XDG_STATE_HOME'):
        return Path(xdg_state) / 'ifcpeek'
    return Path.home() / '.local' / 'state' / 'ifcpeek'

def get_history_file_path() -> Path:
    """Get history file path, creating directory if needed."""
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / 'history'
```

#### 4. Custom Exceptions (`exceptions.py`)
```python
"""Custom exceptions for ifcpeek."""

class IfcPeekError(Exception):
    """Base exception for ifcpeek errors."""
    pass

class FileNotFoundError(IfcPeekError):
    """Raised when IFC file is not found."""
    pass

class InvalidIfcFileError(IfcPeekError):
    """Raised when file is not a valid IFC file."""
    pass
```

## Data Handling Specifications

### IFC Model Loading
- Use `ifcopenshell.open()` for file loading
- Validate file existence before attempting to load
- Handle IfcOpenShell exceptions during loading
- Store model reference for query operations

### Query Processing
- Parse user input to distinguish commands from queries
- Use `ifcopenshell.util.selector.filter_elements(model, query)`
- Handle empty result sets silently
- Output entities using Python's `str()` representation (SPF format)

### Command History
- Store in XDG-compliant location: `~/.local/state/ifcpeek/history`
- No size limits on history file
- UTF-8 encoding for international character support
- Automatic directory creation if not exists

## Error Handling Strategy

### Startup Errors (Exit Immediately)
```python
# File validation
if not self.ifc_file_path.exists():
    raise FileNotFoundError(f"File '{self.ifc_file_path}' not found")

# IFC loading
try:
    model = ifcopenshell.open(str(self.ifc_file_path))
except Exception as e:
    raise InvalidIfcFileError(f"Failed to load IFC file: {e}")
```

### Runtime Errors (Continue Shell Operation)
```python
# Query execution
try:
    results = ifcopenshell.util.selector.filter_elements(self.model, query)
    for entity in results:
        print(entity)
except Exception as e:
    # Print full traceback for debugging
    import traceback
    traceback.print_exc()
```

### Signal Handling
- Ctrl-C: Graceful return to prompt
- Ctrl-D: Clean exit
- SIGTERM: Clean shutdown

## User Interface Specifications

### Prompt Design
- Simple `> ` prompt
- No additional decorations or model information
- Consistent spacing and formatting

### Command Processing
```python
BUILTIN_COMMANDS = {
    r'/help': self._show_help,
    r'/exit': self._exit,
    r'/quit': self._exit,
}

def _process_input(self, user_input: str) -> bool:
    """Process user input, return False to exit."""
    user_input = user_input.strip()
    
    if user_input in self.BUILTIN_COMMANDS:
        return self.BUILTIN_COMMANDS[user_input]()
    elif user_input:  # Non-empty query
        self._execute_query(user_input)
    
    return True
```

### Help System
```python
def _show_help(self) -> bool:
    """Display help information."""
    help_text = """
IfcPeek - Interactive IFC Model Query Tool

USAGE:
  Enter IfcOpenShell selector syntax queries to find matching entities.
  
EXAMPLES:
  IfcWall                           - All walls
  IfcWall, material=concrete        - Concrete walls
  IfcElement, Name=Door-01          - Element named Door-01
  
COMMANDS:
  /help    - Show this help
  /exit    - Exit shell
  /quit    - Exit shell
  Ctrl-D   - Exit shell
  
HISTORY:
  Up/Down  - Navigate command history
  Ctrl-R   - Search command history
  
For selector syntax details, see IfcOpenShell documentation.
"""
    print(help_text)
    return True
```

## Testing Plan

### Test Structure
```python
# tests/conftest.py
import pytest
import tempfile
from pathlib import Path

@pytest.fixture
def valid_ifc_file():
    """Provide path to valid test IFC file."""
    return Path(__file__).parent / 'fixtures' / 'valid_model.ifc'

@pytest.fixture
def invalid_file():
    """Provide path to invalid file."""
    return Path(__file__).parent / 'fixtures' / 'invalid_model.txt'

@pytest.fixture
def temp_history_file():
    """Provide temporary history file."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        yield Path(f.name)
    Path(f.name).unlink(missing_ok=True)
```

### Unit Tests

#### Test Categories
1. **File Loading Tests** (`test_main.py`)
   - Valid IFC file loading
   - Non-existent file handling
   - Invalid IFC file handling
   - Permission errors

2. **Shell Operation Tests** (`test_shell.py`)
   - Query execution with valid syntax
   - Query execution with invalid syntax
   - Empty result handling
   - Built-in command processing

3. **Configuration Tests**
   - XDG directory creation
   - History file management
   - Cross-platform path handling

#### Example Test Cases
```python
def test_valid_ifc_loading(valid_ifc_file):
    """Test successful IFC file loading."""
    shell = IfcPeek(str(valid_ifc_file))
    assert shell.model is not None

def test_file_not_found():
    """Test handling of non-existent files."""
    with pytest.raises(FileNotFoundError):
        IfcPeek("nonexistent.ifc")

def test_query_execution(valid_ifc_file, capsys):
    """Test query execution and output."""
    shell = IfcPeek(str(valid_ifc_file))
    shell._execute_query("IfcWall")
    captured = capsys.readouterr()
    assert "IFCWALL" in captured.out

def test_help_command(valid_ifc_file, capsys):
    """Test help command output."""
    shell = IfcPeek(str(valid_ifc_file))
    result = shell._show_help()
    captured = capsys.readouterr()
    assert "IfcPeek - Interactive IFC Model Query Tool" in captured.out
    assert result is True
```

### Integration Tests
```python
def test_full_shell_session(valid_ifc_file, monkeypatch):
    """Test complete shell session simulation."""
    inputs = iter(['IfcWall', '/help', '/exit'])
    monkeypatch.setattr('builtins.input', lambda _: next(inputs))
    
    shell = IfcPeek(str(valid_ifc_file))
    # Test would need more sophisticated mocking for prompt_toolkit
```

### Test Data Requirements
- **valid_model.ifc**: Minimal valid IFC file with walls, doors, windows
- **invalid_model.txt**: Text file to test invalid format handling
- **large_model.ifc**: Large model for performance testing (optional)

## Deployment and Distribution

### PyPI Package Preparation
```bash
# Build process
python -m build
python -m twine check dist/*
python -m twine upload dist/*
```

### Installation Testing
```bash
# Test installation in clean environment
pip install ifcpeek
ifcpeek test_model.ifc
```

### Cross-Platform Considerations
- Path handling using `pathlib.Path`
- XDG compliance with Windows fallbacks
- Terminal encoding detection
- Signal handling differences

## Development Workflow

### Setup Instructions
```bash
# Development environment setup
git clone <repository>
cd ifcpeek
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -e .[dev]
```

### Development Dependencies
```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "black>=23.0",
    "isort>=5.0",
    "mypy>=1.0",
    "flake8>=6.0",
]
```

### Code Quality Tools
```bash
# Formatting
black src tests
isort src tests

# Linting
flake8 src tests
mypy src

# Testing
pytest tests/ --cov=ifcpeek --cov-report=html
```

## Future Enhancement Architecture

The design supports future features:

### Syntax Highlighting
- prompt_toolkit's `Lexer` interface ready for implementation
- Separate lexer module for IFC selector syntax

### Tab Completion
- prompt_toolkit's `Completer` interface
- Dynamic completion based on loaded model schema

### Additional Output Formats
- Pluggable formatter system
- JSON, CSV, XML output options

### Advanced Query Features
- Query result caching
- Query history with named queries
- Batch query processing

## Performance Considerations

### Memory Management
- Large IFC models may require streaming approaches
- Consider lazy loading for entity details
- Monitor memory usage during development

### Query Optimization
- Cache selector parsing results
- Implement query result limits for large datasets
- Progress indicators for long-running queries

## Security Considerations

### File Access
- Validate file paths to prevent directory traversal
- Limit file access to specified IFC file
- Handle symbolic links appropriately

### Input Validation
- Sanitize user input before processing
- Prevent code injection through query strings
- Validate history file contents

This comprehensive specification provides everything needed for immediate implementation, including code structure, testing strategy, deployment process, and future enhancement roadmap.
