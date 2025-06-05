"""Test configuration with centralized utilities to reduce duplication."""

import os
import stat
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import pytest
from prompt_toolkit.history import FileHistory

# Add src to path if needed
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Add tests to path for test_utils
tests_path = Path(__file__).parent
if str(tests_path) not in sys.path:
    sys.path.insert(0, str(tests_path))

# Now import utilities
from test_utils import MockSetup, get_test_ifc_content


@pytest.fixture
def temp_dir():
    """Provide a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def mock_ifc_file(temp_dir):
    """Create a mock IFC file for testing using centralized content."""
    ifc_file = temp_dir / "test_model.ifc"
    ifc_file.write_text(get_test_ifc_content())
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
    return temp_dir / "history"


@pytest.fixture
def mock_ifcopenshell():
    """Mock ifcopenshell module for testing."""
    return MockSetup.create_mock_model()


@pytest.fixture
def mock_prompt_session():
    """Mock prompt_toolkit PromptSession."""
    session = Mock()
    session.prompt.return_value = "test input"
    return session


@pytest.fixture
def mock_selector():
    """Mock ifcopenshell.util.selector to avoid parsing errors in tests."""
    with patch(
        "ifcpeek.shell.ifcopenshell.util.selector.filter_elements"
    ) as mock_filter:
        mock_filter.return_value = []
        yield mock_filter


@pytest.fixture
def mock_file_history(temp_dir):
    """Mock FileHistory for history testing."""
    history_path = temp_dir / "test_history"
    real_history = FileHistory(str(history_path))

    with patch("ifcpeek.shell.FileHistory", return_value=real_history):
        yield real_history


# Simplified history environment
@pytest.fixture
def history_environment(temp_dir):
    """Set up simplified history testing environment."""
    config_dir = temp_dir / "ifcpeek_config"
    history_path = config_dir / "history"
    config_dir.mkdir(parents=True, exist_ok=True)

    return {
        "config_dir": config_dir,
        "history_path": history_path,
        "temp_dir": temp_dir,
    }


@pytest.fixture
def readonly_directory(temp_dir):
    """Create a read-only directory for permission testing."""
    readonly_dir = temp_dir / "readonly"
    readonly_dir.mkdir()
    readonly_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)  # r-x------

    yield readonly_dir

    # Restore permissions for cleanup
    readonly_dir.chmod(stat.S_IRWXU)  # rwx------


@pytest.fixture
def mock_environment():
    """Provide clean environment for XDG testing."""
    original_env = os.environ.copy()

    def _set_env(**kwargs):
        # Clear XDG variables
        for key in list(os.environ.keys()):
            if key.startswith("XDG_"):
                del os.environ[key]
        # Set new values
        for key, value in kwargs.items():
            os.environ[key] = value

    def _restore_env():
        os.environ.clear()
        os.environ.update(original_env)

    yield _set_env
    _restore_env()


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "history: marks tests related to history")


# Custom assertions (simplified)
def assert_path_exists_and_is_dir(path):
    """Assert that path exists and is a directory."""
    assert path.exists(), f"Path {path} does not exist"
    assert path.is_dir(), f"Path {path} exists but is not a directory"


def assert_path_exists_and_is_file(path):
    """Assert that path exists and is a file."""
    assert path.exists(), f"Path {path} does not exist"
    assert path.is_file(), f"Path {path} exists but is not a file"


# Make custom assertions available to all tests
pytest.assert_path_exists_and_is_dir = assert_path_exists_and_is_dir
pytest.assert_path_exists_and_is_file = assert_path_exists_and_is_file
