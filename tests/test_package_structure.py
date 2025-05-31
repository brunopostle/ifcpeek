"""Test package structure and imports."""

import importlib
import sys
from pathlib import Path

import pytest


def test_main_package_imports():
    """Test that main package imports work correctly."""
    import ifcpeek

    # Test basic imports
    from ifcpeek import exceptions, config, shell, __main__

    # Verify key attributes exist
    assert hasattr(ifcpeek, "__version__")
    assert hasattr(exceptions, "IfcPeekError")
    assert hasattr(config, "get_config_dir")
    assert hasattr(shell, "IfcPeek")
    assert hasattr(__main__, "main")


def test_package_metadata():
    """Test package metadata is accessible."""
    import ifcpeek

    assert ifcpeek.__version__ == "1.0.0"
    assert hasattr(ifcpeek, "__author__")
    assert hasattr(ifcpeek, "__email__")


def test_shell_class_structure():
    """Test shell class has core methods."""
    from ifcpeek.shell import IfcPeek

    expected_methods = [
        "__init__",
        "run",
        "_load_model",
        "_process_input",
        "_execute_query",
        "_show_help",
        "_exit",
    ]

    for method_name in expected_methods:
        assert hasattr(IfcPeek, method_name)
        assert callable(getattr(IfcPeek, method_name))


def test_config_module_functions():
    """Test config module has required functions."""
    from ifcpeek import config

    required_functions = ["get_config_dir", "get_history_file_path"]

    for func_name in required_functions:
        assert hasattr(config, func_name)
        assert callable(getattr(config, func_name))


def test_no_circular_imports():
    """Test that modules can be imported without circular dependencies."""
    modules = [
        "ifcpeek.exceptions",
        "ifcpeek.config",
        "ifcpeek.shell",
        "ifcpeek.__main__",
    ]

    for module_name in modules:
        # Clean import to test for circular dependencies
        if module_name in sys.modules:
            del sys.modules[module_name]

        try:
            importlib.import_module(module_name)
        except ImportError as e:
            pytest.fail(f"Failed to import {module_name}: {e}")


def test_package_files_exist():
    """Test that expected package files exist."""
    import ifcpeek

    package_path = Path(ifcpeek.__file__).parent
    expected_files = [
        "__init__.py",
        "__main__.py",
        "shell.py",
        "config.py",
        "exceptions.py",
    ]

    for filename in expected_files:
        file_path = package_path / filename
        assert file_path.exists(), f"Missing required file: {filename}"
