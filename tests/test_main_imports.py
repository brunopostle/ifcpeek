"""Test main module imports and integration - Fixed for Step 3."""
import sys
from unittest.mock import patch
import pytest


def test_main_imports_config_module():
    """Test that main module can import config."""
    # This should not raise ImportError
    from ifcpeek.__main__ import main
    import ifcpeek.config

    # Verify functions are accessible
    assert hasattr(ifcpeek.config, "get_config_dir")
    assert hasattr(ifcpeek.config, "get_history_file_path")


def test_main_imports_exceptions():
    """Test that main module can import exceptions."""
    from ifcpeek.__main__ import main
    from ifcpeek.exceptions import IfcPeekError

    # Verify exception is usable
    assert issubclass(IfcPeekError, Exception)


def test_no_circular_imports():
    """Test that there are no circular imports between modules."""
    # Clear module cache to test fresh imports
    modules_to_clear = [
        "ifcpeek",
        "ifcpeek.__main__",
        "ifcpeek.config",
        "ifcpeek.exceptions",
        "ifcpeek.shell",
    ]

    for module in modules_to_clear:
        if module in sys.modules:
            del sys.modules[module]

    # Import modules in different orders to test for circular dependencies
    import ifcpeek.exceptions
    import ifcpeek.config
    import ifcpeek.__main__

    # All should be importable without issues
    assert "ifcpeek.exceptions" in sys.modules
    assert "ifcpeek.config" in sys.modules
    assert "ifcpeek.__main__" in sys.modules


def test_main_module_exception_handling_structure():
    """Test that main module has proper exception handling structure."""
    import inspect
    import ifcpeek.__main__ as main_module

    # Get source code of entire module (not just main function)
    source = inspect.getsource(main_module)

    # Verify exception handling imports and usage
    assert "from .exceptions import IfcPeekError" in source
    assert "except IfcPeekError as e:" in source
    assert "except KeyboardInterrupt:" in source


def test_main_implementation_complete():
    """Test that main module implementation is complete (not TODO)."""
    import inspect
    import ifcpeek.__main__ as main_module

    # Get source code of entire module
    source = inspect.getsource(main_module)

    # Verify shell import is present
    assert "from .shell import IfcPeek" in source

    # Verify implementation is complete (Step 3 removes TODO placeholders)
    assert "shell = IfcPeek(args.ifc_file)" in source
    assert "shell.run()" in source

    # Should NOT have TODO comments since Step 3 implements the functionality
    # (Some comments might have "TODO" in explanatory text, but no active TODOs)
    lines = source.split("\n")
    active_todos = [line for line in lines if line.strip().startswith("# TODO:")]
    assert len(active_todos) == 0, f"Found active TODO comments: {active_todos}"
