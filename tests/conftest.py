"""Test configuration with history integration support."""

import os
import stat
import tempfile
import platform
from pathlib import Path
from unittest.mock import Mock, patch
import pytest
from prompt_toolkit.history import FileHistory


@pytest.fixture
def temp_dir():
    """Provide a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def mock_ifc_file(temp_dir):
    """Create a mock IFC file for testing."""
    ifc_file = temp_dir / "test_model.ifc"
    # Create a minimal mock IFC content
    ifc_content = """ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('ViewDefinition [CoordinationView]'),'2;1');
FILE_NAME('test_model.ifc','2024-01-01T00:00:00',('Test Author'),('Test Organization'),'IfcOpenShell','IfcOpenShell','');
FILE_SCHEMA(('IFC4'));
ENDSEC;
DATA;
#1=IFCPROJECT('0u4wgLe6n0ABVaiXyikbkA',$,'Test Project',$,$,$,$,(#2),#3);
#2=IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,#4,$);
#3=IFCUNITASSIGNMENT((#5));
#4=IFCAXIS2PLACEMENT3D(#6,$,$);
#5=IFCSIUNIT(*,.LENGTHUNIT.,.MILLI.,.METRE.);
#6=IFCCARTESIANPOINT((0.,0.,0.));
ENDSEC;
END-ISO-10303-21;"""
    ifc_file.write_text(ifc_content)
    return ifc_file


@pytest.fixture
def invalid_file(temp_dir):
    """Create an invalid file (not IFC) for testing."""
    invalid = temp_dir / "invalid.txt"
    invalid.write_text("This is not an IFC file.")
    return invalid


@pytest.fixture
def nonexistent_file(temp_dir):
    """Provide path to a nonexistent file."""
    return temp_dir / "nonexistent.ifc"


@pytest.fixture
def temp_history_file(temp_dir):
    """Provide temporary history file."""
    history_file = temp_dir / "history"
    return history_file


@pytest.fixture
def mock_ifcopenshell():
    """Mock ifcopenshell module for testing."""
    mock_model = Mock()
    mock_model.schema = "IFC4"

    mock_ifcopenshell = Mock()
    mock_ifcopenshell.open.return_value = mock_model

    return mock_ifcopenshell


@pytest.fixture
def mock_prompt_session():
    """Mock prompt_toolkit PromptSession."""
    session = Mock()
    session.prompt.return_value = "test input"
    return session


@pytest.fixture
def mock_selector():
    """Mock ifcopenshell.util.selector to avoid parsing errors in tests.

    This fixture is CRITICAL for Step 7+ tests - it mocks the real IFC selector
    to avoid syntax errors when testing with invalid IFC queries.
    """
    with patch(
        "ifcpeek.shell.ifcopenshell.util.selector.filter_elements"
    ) as mock_filter:
        # Default behavior: return empty results for any query
        mock_filter.return_value = []
        yield mock_filter


@pytest.fixture
def mock_file_history(temp_dir):
    """Mock FileHistory for history testing."""
    history_path = temp_dir / "test_history"

    # Create real FileHistory for more realistic testing
    real_history = FileHistory(str(history_path))

    with patch("ifcpeek.shell.FileHistory", return_value=real_history):
        yield real_history


@pytest.fixture
def history_test_environment(temp_dir):
    """Set up complete history testing environment."""
    config_dir = temp_dir / "ifcpeek_config"
    history_path = config_dir / "history"

    # Ensure directory exists
    config_dir.mkdir(parents=True, exist_ok=True)

    return {
        "config_dir": config_dir,
        "history_path": history_path,
        "temp_dir": temp_dir,
    }


@pytest.fixture
def mock_history_integration(history_test_environment):
    """Mock complete history integration for testing."""
    env = history_test_environment

    # Create real FileHistory
    real_history = FileHistory(str(env["history_path"]))

    # Mock the configuration functions
    def mock_get_history_path():
        env["config_dir"].mkdir(parents=True, exist_ok=True)
        return env["history_path"]

    with patch(
        "ifcpeek.config.get_history_file_path", side_effect=mock_get_history_path
    ):
        with patch("ifcpeek.shell.FileHistory", return_value=real_history):
            yield {
                "history": real_history,
                "config_dir": env["config_dir"],
                "history_path": env["history_path"],
            }


@pytest.fixture
def readonly_directory(temp_dir):
    """Create a read-only directory for permission testing."""
    readonly_dir = temp_dir / "readonly"
    readonly_dir.mkdir()

    # Make directory read-only
    readonly_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)  # r-x------

    yield readonly_dir

    # Restore permissions for cleanup
    readonly_dir.chmod(stat.S_IRWXU)  # rwx------


@pytest.fixture
def mock_environment():
    """Provide clean environment for XDG testing."""
    original_env = os.environ.copy()

    def _set_env(**kwargs):
        """Set specific environment variables."""
        # Clear XDG variables
        for key in list(os.environ.keys()):
            if key.startswith("XDG_"):
                del os.environ[key]

        # Set new values
        for key, value in kwargs.items():
            os.environ[key] = value

    def _restore_env():
        """Restore original environment."""
        os.environ.clear()
        os.environ.update(original_env)

    yield _set_env
    _restore_env()


@pytest.fixture
def platform_mock():
    """Mock platform detection for cross-platform testing."""
    original_system = platform.system

    def _mock_system(system_name):
        """Mock platform.system to return specific value."""
        return patch("platform.system", return_value=system_name)

    yield _mock_system

    # Restore original
    platform.system = original_system


@pytest.fixture
def mock_home_directory(temp_dir):
    """Mock Path.home() to return test directory."""
    fake_home = temp_dir / "home" / "testuser"
    fake_home.mkdir(parents=True)

    with patch("pathlib.Path.home", return_value=fake_home):
        yield fake_home


@pytest.fixture
def file_with_special_chars(temp_dir):
    """Create files with special characters for testing."""
    special_files = {}

    # Test various special characters
    special_names = [
        "file with spaces.ifc",
        "file(with)parentheses.ifc",
        "file[with]brackets.ifc",
        "file&with&ampersand.ifc",
        "file$with$dollar.ifc",
        "file@with@at.ifc",
        "测试文件.ifc",  # Unicode
        "файл.ifc",  # Cyrillic
    ]

    for name in special_names:
        try:
            file_path = temp_dir / name
            file_path.write_text("ISO-10303-21;")
            special_files[name] = file_path
        except (OSError, UnicodeError):
            # Skip if file system doesn't support this character
            pass

    yield special_files


@pytest.fixture
def deep_directory_structure(temp_dir):
    """Create deep directory structure for path length testing."""
    deep_path = temp_dir

    # Create nested directories
    for i in range(10):
        deep_path = deep_path / f"very_long_directory_name_level_{i:02d}"

    deep_path.mkdir(parents=True)

    # Create IFC file at the deepest level
    ifc_file = deep_path / "deeply_nested_test_file.ifc"
    ifc_file.write_text("ISO-10303-21;")

    yield ifc_file


@pytest.fixture
def symlink_file(temp_dir):
    """Create symbolic link for testing (skip if not supported)."""
    original = temp_dir / "original.ifc"
    original.write_text("ISO-10303-21;")

    symlink = temp_dir / "symlink.ifc"

    try:
        symlink.symlink_to(original)
        yield symlink
    except OSError:
        # Skip if symlinks not supported
        pytest.skip("Symbolic links not supported on this platform")


@pytest.fixture
def unicode_history_commands():
    """Provide Unicode test commands for history testing."""
    return [
        "IfcWall, Name=测试墙体",  # Chinese
        "IfcDoor, Name=Дверь",  # Cyrillic
        "IfcWindow, Name=Fenêtre",  # French accents
        "IfcSlab, Material=Béton",  # French accents
        "IfcBeam, Tag=§pecial©har$",  # Special symbols
        'IfcColumn, Description="Wall with spaces"',  # Quoted strings
        "IfcWall | IfcDoor",  # Pipe operators
        "IfcWall, height>3.0",  # Comparison operators
    ]


@pytest.fixture
def large_history_dataset():
    """Provide large dataset for history performance testing."""
    commands = []

    # Generate realistic IFC queries
    element_types = [
        "IfcWall",
        "IfcDoor",
        "IfcWindow",
        "IfcSlab",
        "IfcBeam",
        "IfcColumn",
    ]
    materials = ["concrete", "steel", "wood", "glass", "aluminum"]

    for i in range(100):
        element = element_types[i % len(element_types)]
        if i % 3 == 0:
            # Simple query
            commands.append(f"{element}")
        elif i % 3 == 1:
            # Query with material
            material = materials[i % len(materials)]
            commands.append(f"{element}, material={material}")
        else:
            # Query with name
            commands.append(f"{element}, Name=Test{element[3:]}-{i:03d}")

    # Add some commands
    for i in range(0, 100, 10):
        commands.insert(i, "/help")

    return commands


@pytest.fixture
def concurrent_history_setup(temp_dir):
    """Set up concurrent history access testing."""
    history_path = temp_dir / "concurrent_history"

    def create_history_instance():
        return FileHistory(str(history_path))

    return {"history_path": history_path, "create_instance": create_history_instance}


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line(
        "markers", "xdg: marks tests that require XDG environment testing"
    )
    config.addinivalue_line(
        "markers", "permissions: marks tests that require permission manipulation"
    )
    config.addinivalue_line(
        "markers", "history: marks tests related to history functionality"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests that check performance characteristics"
    )


# Custom assertions for better error messages
def assert_path_exists_and_is_dir(path):
    """Assert that path exists and is a directory."""
    assert path.exists(), f"Path {path} does not exist"
    assert path.is_dir(), f"Path {path} exists but is not a directory"


def assert_path_exists_and_is_file(path):
    """Assert that path exists and is a file."""
    assert path.exists(), f"Path {path} does not exist"
    assert path.is_file(), f"Path {path} exists but is not a file"


def assert_exception_chain(exception, expected_cause_type=None):
    """Assert exception chaining is correct."""
    if expected_cause_type:
        assert exception.__cause__ is not None, "Exception should have a cause"
        assert isinstance(
            exception.__cause__, expected_cause_type
        ), f"Expected cause type {expected_cause_type}, got {type(exception.__cause__)}"


def assert_history_contains_commands(history, expected_commands):
    """Assert that history contains all expected commands."""
    if hasattr(history, "get_strings"):
        history_strings = list(history.get_strings())
        for cmd in expected_commands:
            assert cmd in history_strings, f"Command '{cmd}' not found in history"
    else:
        pytest.skip("History object doesn't support get_strings method")


def assert_unicode_preserved_in_history(history, unicode_commands):
    """Assert that Unicode commands are preserved correctly in history."""
    if hasattr(history, "get_strings"):
        history_strings = list(history.get_strings())
        for cmd in unicode_commands:
            assert (
                cmd in history_strings
            ), f"Unicode command '{cmd}' not preserved in history"
    else:
        pytest.skip("History object doesn't support get_strings method")


# Make custom assertions available to all tests
pytest.assert_path_exists_and_is_dir = assert_path_exists_and_is_dir
pytest.assert_path_exists_and_is_file = assert_path_exists_and_is_file
pytest.assert_exception_chain = assert_exception_chain
pytest.assert_history_contains_commands = assert_history_contains_commands
pytest.assert_unicode_preserved_in_history = assert_unicode_preserved_in_history
