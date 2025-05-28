"""Test package structure and imports."""

import importlib
import sys
from pathlib import Path

import pytest


def test_package_imports():
    """Test that all package modules can be imported."""
    # Test main package import
    import ifcpeek

    assert hasattr(ifcpeek, "__version__")
    assert ifcpeek.__version__ == "1.0.0"

    # Test submodule imports
    from ifcpeek import exceptions
    from ifcpeek import config
    from ifcpeek import shell
    from ifcpeek import __main__

    # Verify modules are actually modules
    assert hasattr(exceptions, "IfcPeekError")
    assert hasattr(config, "get_config_dir")
    assert hasattr(shell, "IfcPeek")
    assert hasattr(__main__, "main")


def test_package_metadata():
    """Test package metadata is accessible."""
    import ifcpeek

    # Test version info
    assert ifcpeek.__version__ == "1.0.0"
    assert ifcpeek.__author__ == "Bruno Postle"
    assert ifcpeek.__email__ == "bruno@postle.net"
    assert ifcpeek.__license__ == "GPLv3"


def test_package_all_exports():
    """Test __all__ exports are valid."""
    import ifcpeek

    # Verify __all__ exists and contains expected items
    expected_exports = [
        "__version__",
        "IfcPeek",
        "IfcPeekError",
        "FileNotFoundError",
        "InvalidIfcFileError",
    ]

    assert hasattr(ifcpeek, "__all__")
    for export in expected_exports:
        assert export in ifcpeek.__all__
        assert hasattr(ifcpeek, export)


def test_exception_hierarchy():
    """Test exception class hierarchy."""
    from ifcpeek.exceptions import (
        IfcPeekError,
        FileNotFoundError,
        InvalidIfcFileError,
        QueryExecutionError,
        ConfigurationError,
    )

    # Test inheritance
    assert issubclass(FileNotFoundError, IfcPeekError)
    assert issubclass(InvalidIfcFileError, IfcPeekError)
    assert issubclass(QueryExecutionError, IfcPeekError)
    assert issubclass(ConfigurationError, IfcPeekError)

    # Test base class inherits from Exception
    assert issubclass(IfcPeekError, Exception)


def test_config_module_functions():
    """Test config module functions exist and are callable."""
    from ifcpeek import config

    functions = [
        "get_config_dir",
        "get_history_file_path",
        "get_cache_dir",
        "validate_ifc_file_path",
    ]

    for func_name in functions:
        assert hasattr(config, func_name)
        func = getattr(config, func_name)
        assert callable(func)


def test_shell_class_structure():
    """Test shell class has expected structure."""
    from ifcpeek.shell import IfcPeek

    # Test class exists and is callable
    assert callable(IfcPeek)

    # Test expected methods exist (at class level)
    expected_methods = [
        "__init__",
        "run",
        "_load_model",
        "_create_session",
        "_process_input",
        "_execute_query",
        "_show_help",
        "_exit",
    ]

    for method_name in expected_methods:
        assert hasattr(IfcPeek, method_name)
        method = getattr(IfcPeek, method_name)
        assert callable(method)


def test_main_module_structure():
    """Test main module has expected structure."""
    from ifcpeek import __main__

    # Test main function exists
    assert hasattr(__main__, "main")
    assert callable(__main__.main)


def test_module_file_locations():
    """Test that modules are in expected locations."""
    import ifcpeek

    # Get package path
    package_path = Path(ifcpeek.__file__).parent

    # Expected files
    expected_files = [
        "__init__.py",
        "__main__.py",
        "shell.py",
        "config.py",
        "exceptions.py",
    ]

    for filename in expected_files:
        file_path = package_path / filename
        assert file_path.exists(), f"Expected file {filename} not found"
        assert file_path.is_file(), f"{filename} is not a file"


def test_no_circular_imports():
    """Test that there are no circular import issues."""
    # This test imports each module individually to check for circular imports
    modules = [
        "ifcpeek",
        "ifcpeek.exceptions",
        "ifcpeek.config",
        "ifcpeek.shell",
        "ifcpeek.__main__",
    ]

    for module_name in modules:
        try:
            # Force reload to test fresh import
            if module_name in sys.modules:
                del sys.modules[module_name]
            module = importlib.import_module(module_name)
            assert module is not None
        except ImportError as e:
            pytest.fail(f"Failed to import {module_name}: {e}")


def test_graceful_dependency_handling():
    """Test that missing optional dependencies are handled gracefully."""
    # Test that shell module can be imported even if optional deps are missing
    from ifcpeek import shell

    # The module should define availability flags
    assert hasattr(shell, "PROMPT_TOOLKIT_AVAILABLE")
    assert hasattr(shell, "IFCOPENSHELL_AVAILABLE")

    # These should be boolean values
    assert isinstance(shell.PROMPT_TOOLKIT_AVAILABLE, bool)
    assert isinstance(shell.IFCOPENSHELL_AVAILABLE, bool)
