# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

IfcPeek is an interactive command-line tool for querying IFC (Industry Foundation Classes) building models using IfcOpenShell's selector syntax. It provides a Unix shell-like interface with intelligent tab completion, value extraction, and CSV export capabilities for BIM professionals.

## Essential Development Commands

### Testing
```bash
# Run all tests with verbose output
python -m pytest tests/ -v

# Run specific test file
pytest tests/test_completion.py -v

# Run specific test function
pytest tests/test_shell.py::test_query_execution -v

# Run with coverage report
pytest tests/ --cov=ifcpeek --cov-report=html
```

### Code Quality
```bash
# Format code (Black + isort)
black src tests
isort src tests

# Type checking
mypy src

# Linting
flake8 src tests
```

### Installation
```bash
# Development installation (editable mode)
pip install -e .

# With development dependencies
pip install -e ".[dev]"

# Core dependencies only
pip install ifcopenshell prompt_toolkit
```

### Running the Application
```bash
# Interactive mode
ifcpeek path/to/model.ifc

# With debug output
ifcpeek --debug path/to/model.ifc

# With verbose startup info
ifcpeek --verbose path/to/model.ifc

# Non-interactive mode (piped input)
echo 'IfcWall ; Name' | ifcpeek model.ifc

# With CSV headers
echo 'IfcWall ; Name ; type.Name' | ifcpeek --headers model.ifc > output.csv
```

## Architecture Overview

### Dual-Mode Architecture

IfcPeek operates in two distinct modes detected automatically via `sys.stdin.isatty()` and `sys.stdout.isatty()`:

1. **Interactive Mode**: Full prompt_toolkit interface with tab completion, history, and syntax highlighting
2. **Non-Interactive Mode**: Silent piped input processing with clean stdout for CSV output

Key implementation: `shell.py:_is_interactive_mode()` and `shell.py:run()`

### Query Processing Pipeline

```
User Input → Parser → Filter Query → IfcOpenShell Selector → Results
                   ↓
              Value Queries → Value Extractor → Formatter → Output
```

1. **Input Parsing** (`shell.py:_parse_combined_query()`): Splits queries on semicolon into filter and value parts
2. **Filter Execution** (`shell.py:_execute_query()`): Uses `ifcopenshell.util.selector.filter_elements()` exclusively
3. **Value Extraction** (`value_extraction.py`): Two-phase approach:
   - Phase 1: Extract raw values using `ifcopenshell.util.selector.get_element_value()`
   - Phase 2: Apply formatting functions (upper, lower, round, concat, etc.)
4. **Output Formatting** (`formatters.py`): SPF format with optional ANSI syntax highlighting

### Completion System Architecture

Located in `completion.py`, the completion system is one of the most complex parts:

- **Context-Aware**: Analyzes query position (before/after semicolon) to provide different completions
- **Model-Driven**: Scans actual IFC model to discover available classes, property sets, and attributes
- **Schema-Aware**: Traverses IFC schema hierarchy to include abstract parent classes (e.g., IfcBuildingElement)
- **Dynamic**: Samples filtered elements to discover their properties and attributes
- **Intelligent Sampling**: Samples up to 50 elements (increased from 5) for better attribute discovery
- **Lazy-Loading**: Builds caches on-demand to minimize startup time

Key methods:
- `completion.py:create_completion_system()`: Entry point that builds the completer
- `IfcCompleter.get_completions()`: Routes to filter or value completion handlers
- `IfcCompleter._get_ifc_classes()`: Collects IFC classes including parent classes via schema traversal
- Filter completions: IFC classes, attributes, keywords (material, type, location), property sets
- Value completions: Context-aware based on filtered element types, includes relationship attributes

**Important Schema Access**: The completion system uses `ifcopenshell.ifcopenshell_wrapper.schema_by_name()` to access the IFC schema object. Note that `model.schema` is a string (e.g., "IFC4"), not the schema object itself. The schema object provides `declaration_by_name()` for class definitions and `supertype()` methods for hierarchy traversal.

**Sampling Strategy**: Value context completions sample up to 50 elements to discover attributes and properties. Filter context processes all elements returned by queries. This balances performance with completeness.

**Tuple/List Handling**: When completing paths that resolve to tuples or lists (e.g., relationship attributes like `ConnectedTo`), the system only offers appropriate completions like `count` and numeric indices, not general selector keywords.

### Value Extraction System

The value extraction system (`value_extraction.py:ValueExtractor`) handles two types of queries:

1. **Raw Values**: Direct attribute/property access (e.g., `Name`, `type.Name`, `Pset_WallCommon.FireRating`)
2. **Formatted Values**: Function-wrapped queries (e.g., `upper(Name)`, `round(type.Width, 0.1)`)

Critical constraint: All operations must use IfcOpenShell's `get_element_value()` function, never direct entity attribute access.

## Integration Guidelines

### IfcOpenShell Integration

**CRITICAL**: All IFC queries MUST use `ifcopenshell.util.selector` functions:
- Use `filter_elements(model, query)` for filtering
- Use `get_element_value(element, path)` for value extraction
- Never access entity attributes directly (e.g., `entity.Name`)

This ensures compatibility with IfcOpenShell's selector syntax including property sets, relationships, and formatting functions.

### Output Handling

**Strict separation of output streams**:
- **stdout**: Clean data only (SPF format or CSV values)
- **stderr**: All debug, error, warning, and status messages

This enables piped workflows where stdout can be redirected to CSV files without contamination.

Implementation: All print statements use `file=sys.stderr` except for actual query results.

### Debug System

Configurable debug output via environment variables:
- `IFCPEEK_DEBUG=1`: Detailed debug information
- `IFCPEEK_VERBOSE=1`: Startup and status messages

Managed by `debug.py:DebugManager` with convenience functions:
- `debug_print()`: Only shown when debug enabled
- `verbose_print()`: Shown when verbose or debug enabled
- `error_print()` / `warning_print()`: Always shown

### Signal Handling

Signal behavior differs by mode:
- **Interactive**: Ctrl-C shows reminder to use Ctrl-D, continues running
- **Non-Interactive**: Ctrl-C exits immediately

Implementation: `shell.py:_setup_signal_handlers()`

## Key Files and Responsibilities

- `__main__.py`: Entry point, argument parsing, error handling
- `shell.py`: Main shell class, mode detection, query processing
- `completion.py`: Tab completion system (complex, model-driven)
- `value_extraction.py`: Value extraction and formatting logic
- `formatters.py`: SPF output formatting and ANSI syntax highlighting
- `config.py`: XDG-compliant paths, file validation
- `exceptions.py`: Custom exception hierarchy with context
- `debug.py`: Configurable debug output system

## Important Design Patterns

### XDG Compliance

Configuration follows XDG Base Directory specification:
- History: `~/.local/state/ifcpeek/history`
- Respects `XDG_STATE_HOME` environment variable

### Error Context

Custom exceptions carry context for better debugging:
```python
raise InvalidIfcFileError(
    "message",
    file_path=path,
    file_size=size,
    error_type="InvalidExtension"
)
```

### Lazy Initialization

The completion system uses lazy loading to avoid expensive model scans at startup. Caches are built on first access.

## Common Development Patterns

### Adding New Commands

1. Add command to `shell.py:BUILTIN_COMMANDS` dict
2. Implement handler method (returns bool: True to continue, False to exit)
3. Update help text in `_show_help()`

### Adding Formatting Functions

Formatting functions are handled by IfcOpenShell's selector syntax. IfcPeek passes queries through unchanged, so new functions work automatically if supported by IfcOpenShell.

### Modifying Completion Behavior

The completion system is complex. Key areas:
- `completion.py:IfcCompleter._get_filter_completions()`: Filter context completions
- `completion.py:IfcCompleter._get_value_completions()`: Value extraction completions
- `completion.py:IfcCompleter._determine_filter_completion_type()`: Context detection logic
- `completion.py:IfcCompleter._resolve_value_path_completions()`: Value path resolution
- Add new keywords to `selector_keywords` or `filter_keywords` sets

**Important implementation details**:

1. **Schema Traversal**: Uses `ifcopenshell.ifcopenshell_wrapper.schema_by_name(model.schema)` to get the schema object, then `declaration_by_name(class_name)` to get class definitions. The `supertype()` method (not property!) returns the parent class declaration.

2. **Filter Extraction**: When completing incomplete filter queries (e.g., `IfcWall, Pset_WallCommon.` or `IfcWall, Name=`), the system must extract a valid filter by removing the incomplete part before calling `filter_elements()`. Helper methods `_extract_cumulative_filter_before_pset_dot()` and `_extract_cumulative_filter_before_equals()` handle this.

3. **Sampling Strategy**: Value completions sample up to 50 elements (`elements[:50]`). Filter attribute extraction processes all filtered elements for accuracy.

4. **Tuple Detection**: Path completions check if results are tuples/lists and conditionally add selector keywords. Tuples get `count` and numeric indices; objects get selector keywords like `building`, `type`, etc.

## Testing Strategy

Tests follow pytest conventions:
- Test files: `tests/test_*.py`
- Fixtures: `tests/conftest.py`
- Test model fixtures: `tests/fixtures/` (empty in current codebase)

Key test areas:
- Interactive vs non-interactive mode detection
- Query parsing and execution
- Value extraction with formatting
- Completion system behavior (extensive regression tests in `test_completion_regressions.py`)
- Error handling and edge cases

### Completion System Testing

`tests/test_completion_regressions.py` contains comprehensive regression tests covering:
- Space after IFC class completion
- Property completion in filter and value contexts
- Attribute value completion
- Relationship attribute discovery
- Tuple/list result handling
- Parent class inclusion via schema hierarchy

The test suite uses extensive mocking to simulate IfcOpenShell behavior without requiring actual IFC files. Key mocking areas:
- `ifcopenshell.util.selector.filter_elements`
- `ifcopenshell.util.selector.get_element_value`
- `ifcopenshell.util.element.get_psets`
- `ifcopenshell.ifcopenshell_wrapper.schema_by_name` (returns mock schema with proper hierarchy)

## Development Philosophy

**Note from README**: This is an experimental application developed using LLM-assisted code generation. The codebase emphasizes:
- Comprehensive error handling and debugging capabilities
- Separation of concerns (interactive vs non-interactive)
- Integration with IfcOpenShell (never reimplementing IFC logic)
- Clean output suitable for CSV export and scripting

When making changes, maintain these principles and ensure both interactive and piped modes continue working correctly.
