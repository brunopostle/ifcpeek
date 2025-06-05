"""
Centralized test utilities to reduce duplication across test files.
"""

import tempfile
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

# Ensure src is in path
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from ifcpeek.shell import IfcPeek


class MockSetup:
    """Centralized mock setup for consistent test configuration."""

    @staticmethod
    def create_mock_model(schema="IFC4", entities=None, by_type_return=None):
        """Create a mock IFC model with standard configuration."""
        mock_model = Mock()
        mock_model.schema = schema

        # Setup entity iteration
        if entities:
            mock_model.__iter__ = Mock(return_value=iter(entities))
        else:
            mock_model.__iter__ = Mock(return_value=iter([]))

        # Setup by_type method
        if by_type_return is not None:
            mock_model.by_type.return_value = by_type_return
        else:
            mock_model.by_type.return_value = []

        return mock_model

    @staticmethod
    def create_mock_wall_entity(wall_id=1, name="TestWall", guid="wall-guid-001"):
        """Create a mock wall entity with standard properties."""
        mock_wall = Mock()
        mock_wall.id.return_value = wall_id
        mock_wall.is_a.return_value = "IfcWall"
        mock_wall.Name = name
        mock_wall.GlobalId = guid
        mock_wall.__str__ = Mock(
            return_value=f"#{wall_id}=IFCWALL('{guid}',$,$,'{name}',$,$,$,$,$);"
        )
        return mock_wall

    @staticmethod
    def create_mock_door_entity(door_id=2, name="TestDoor", guid="door-guid-001"):
        """Create a mock door entity with standard properties."""
        mock_door = Mock()
        mock_door.id.return_value = door_id
        mock_door.is_a.return_value = "IfcDoor"
        mock_door.Name = name
        mock_door.GlobalId = guid
        mock_door.__str__ = Mock(
            return_value=f"#{door_id}=IFCDOOR('{guid}',$,$,'{name}',$,$,$,$,$);"
        )
        return mock_door


class ShellTestBase:
    """Base class for shell tests with common setup."""

    @pytest.fixture
    def mock_model(self):
        """Standard mock model fixture."""
        return MockSetup.create_mock_model()

    @pytest.fixture
    def mock_wall(self):
        """Standard mock wall fixture."""
        return MockSetup.create_mock_wall_entity()

    @pytest.fixture
    def mock_door(self):
        """Standard mock door fixture."""
        return MockSetup.create_mock_door_entity()

    @pytest.fixture
    def shell_with_mocks(self, mock_ifc_file, mock_model):
        """Create shell instance with mocked dependencies."""
        with patch("ifcpeek.shell.ifcopenshell.open", return_value=mock_model):
            return IfcPeek(str(mock_ifc_file), force_interactive=True)

    @pytest.fixture
    def shell_non_interactive(self, mock_ifc_file, mock_model):
        """Create shell instance in non-interactive mode."""
        with patch("ifcpeek.shell.ifcopenshell.open", return_value=mock_model):
            with patch("sys.stdin.isatty", return_value=False):
                with patch("sys.stdout.isatty", return_value=False):
                    return IfcPeek(str(mock_ifc_file))


class QueryTestMixin:
    """Mixin for tests that need query execution mocking."""

    def setup_successful_query_mock(self, mock_selector, entities):
        """Setup mock_selector for successful query with given entities."""
        mock_selector.return_value = entities
        mock_selector.side_effect = None

    def setup_failing_query_mock(self, mock_selector, exception=None):
        """Setup mock_selector for failing query."""
        if exception is None:
            exception = Exception("Mock query failure")
        mock_selector.side_effect = exception
        mock_selector.return_value = []

    def setup_empty_query_mock(self, mock_selector):
        """Setup mock_selector for empty results."""
        mock_selector.return_value = []
        mock_selector.side_effect = None


class ValueExtractionTestMixin:
    """Mixin for tests that need value extraction mocking."""

    def setup_value_extraction_mock(self, mock_get_value, value_map):
        """Setup value extraction mock with a value mapping."""

        def side_effect(element, query):
            return value_map.get(query, "")

        mock_get_value.side_effect = side_effect

    def setup_failing_value_extraction(self, mock_get_value, exception=None):
        """Setup value extraction to fail."""
        if exception is None:
            exception = Exception("Property not found")
        mock_get_value.side_effect = exception


def get_test_ifc_content():
    """Standard IFC file content for testing."""
    return """ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('ViewDefinition [CoordinationView]'),'2;1');
FILE_NAME('test_model.ifc','2024-01-01T00:00:00',('Test'),('Test'),'IfcOpenShell','IfcOpenShell','');
FILE_SCHEMA(('IFC4'));
ENDSEC;
DATA;
#1=IFCPROJECT('guid',$,'Test Project',$,$,$,$,(#2),#3);
#2=IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,#4,$);
#3=IFCUNITASSIGNMENT((#5));
#4=IFCAXIS2PLACEMENT3D(#6,$,$);
#5=IFCSIUNIT(*,.LENGTHUNIT.,.MILLI.,.METRE.);
#6=IFCCARTESIANPOINT((0.,0.,0.));
#7=IFCWALL('wall-guid',$,$,'TestWall',$,$,$,$,$);
#8=IFCDOOR('door-guid',$,$,'TestDoor',$,$,$,$,$);
ENDSEC;
END-ISO-10303-21;"""


@pytest.fixture
def temp_ifc_content():
    """Fixture that provides standard IFC file content for testing."""
    return get_test_ifc_content()


@pytest.fixture
def temp_ifc_file_from_content():
    """Create temporary IFC file from content."""
    temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".ifc", delete=False)
    temp_file.write(get_test_ifc_content())
    temp_file.close()

    yield Path(temp_file.name)

    try:
        os.unlink(temp_file.name)
    except:
        pass


# Context managers for common patching scenarios
class MockIfcEnvironment:
    """Context manager for mocking IFC environment."""

    def __init__(self, model=None, selector_return=None, selector_exception=None):
        self.model = model or MockSetup.create_mock_model()
        self.selector_return = selector_return or []
        self.selector_exception = selector_exception

    def __enter__(self):
        self.open_patch = patch(
            "ifcpeek.shell.ifcopenshell.open", return_value=self.model
        )
        self.selector_patch = patch(
            "ifcpeek.shell.ifcopenshell.util.selector.filter_elements"
        )

        self.mock_open = self.open_patch.__enter__()
        self.mock_selector = self.selector_patch.__enter__()

        if self.selector_exception:
            self.mock_selector.side_effect = self.selector_exception
        else:
            self.mock_selector.return_value = self.selector_return

        return self.mock_open, self.mock_selector

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.selector_patch.__exit__(exc_type, exc_val, exc_tb)
        self.open_patch.__exit__(exc_type, exc_val, exc_tb)


# Assertion helpers
def assert_query_output_contains(capsys, expected_text):
    """Assert that query output contains expected text."""
    captured = capsys.readouterr()
    assert (
        expected_text in captured.out
    ), f"Expected '{expected_text}' in output: '{captured.out}'"


def assert_error_output_contains(capsys, expected_text):
    """Assert that error output contains expected text."""
    captured = capsys.readouterr()
    assert (
        expected_text in captured.err
    ), f"Expected '{expected_text}' in stderr: '{captured.err}'"


def assert_no_stdout_output(capsys):
    """Assert that no output was produced to stdout."""
    captured = capsys.readouterr()
    assert (
        captured.out.strip() == ""
    ), f"Expected no stdout output, got: '{captured.out}'"
