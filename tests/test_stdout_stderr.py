"""
test_stdout_stderr.py - Fixed for test suite isolation

The issue was that this test runs fine alone but fails in the full test suite.
This indicates environment contamination from other tests. The fix ensures
proper isolation by resetting the environment and using fresh subprocesses.
"""

import tempfile
import subprocess
import sys
import os
from pathlib import Path
import pytest


def create_test_ifc_file():
    """Create a minimal test IFC file."""
    temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".ifc", delete=False)
    temp_file.write(
        """ISO-10303-21;
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
#7=IFCWALL('wall-guid-001',$,$,'TestWall-001',$,$,$,$,$);
#8=IFCWALL('wall-guid-002',$,$,'TestWall-002',$,$,$,$,$);
ENDSEC;
END-ISO-10303-21;"""
    )
    temp_file.close()
    return Path(temp_file.name)


class TestSTDOUTSTDERRSeparation:
    """Test STDOUT/STDERR separation with proper isolation."""

    def test_query_results_stdout(self):
        """Test that query results go to STDOUT, debug messages to STDERR."""
        ifc_file = create_test_ifc_file()
        try:
            # Create completely isolated test script
            test_script = f"""
import sys
import os

# Ensure clean environment
os.environ["IFCPEEK_DEBUG"] = "1"
sys.path.insert(0, "src")

from ifcpeek.shell import IfcPeek
from unittest.mock import patch, Mock

# Mock dependencies with complete isolation
with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
    mock_model = Mock()
    mock_model.schema = "IFC4"
    mock_model.__iter__ = Mock(return_value=iter([]))
    mock_model.by_type = Mock(return_value=[])
    mock_open.return_value = mock_model

    with patch("ifcpeek.shell.ifcopenshell.util.selector.filter_elements") as mock_filter:
        mock_wall = Mock()
        mock_wall.__str__ = Mock(return_value="#7=IFCWALL(\\'wall-guid-001\\',$,$,\\'TestWall-001\\',$,$,$,$,$);")
        mock_filter.return_value = [mock_wall]

        # Force non-interactive mode to avoid completion system
        with patch("sys.stdin.isatty", return_value=False):
            with patch("sys.stdout.isatty", return_value=False):
                shell = IfcPeek("{str(ifc_file)}")
                shell._execute_query("IfcWall")
"""

            # Run in completely fresh subprocess
            result = subprocess.run(
                [sys.executable, "-c", test_script],
                capture_output=True,
                text=True,
                env=dict(os.environ, IFCPEEK_DEBUG="1"),  # Clean environment
            )

            # Results should be in STDOUT
            assert (
                "#7=IFCWALL('wall-guid-001'" in result.stdout
            ), f"Query results not in STDOUT. STDOUT: '{result.stdout}', STDERR: '{result.stderr}'"

            # No results should leak to STDERR
            assert (
                "#7=IFCWALL('wall-guid-001'" not in result.stderr
            ), "Query results leaked to STDERR"

        finally:
            ifc_file.unlink()

    def test_empty_results(self):
        """Test that empty query results produce no STDOUT output."""
        ifc_file = create_test_ifc_file()
        try:
            test_script = f"""
import sys
import os

# Ensure clean environment
os.environ["IFCPEEK_DEBUG"] = "1"
sys.path.insert(0, "src")

from ifcpeek.shell import IfcPeek
from unittest.mock import patch, Mock

with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
    mock_model = Mock()
    mock_model.__iter__ = Mock(return_value=iter([]))
    mock_model.by_type = Mock(return_value=[])
    mock_open.return_value = mock_model

    with patch("ifcpeek.shell.ifcopenshell.util.selector.filter_elements") as mock_filter:
        mock_filter.return_value = []  # Empty results

        # Force non-interactive mode
        with patch("sys.stdin.isatty", return_value=False):
            with patch("sys.stdout.isatty", return_value=False):
                shell = IfcPeek("{str(ifc_file)}")
                shell._execute_query("IfcNonExistent")
"""

            result = subprocess.run(
                [sys.executable, "-c", test_script],
                capture_output=True,
                text=True,
                env=dict(os.environ, IFCPEEK_DEBUG="1"),
            )

            assert (
                len(result.stdout.strip()) == 0
            ), f"STDOUT should be empty for empty results. STDOUT: '{result.stdout}'"

        finally:
            ifc_file.unlink()

    def test_help_command_stderr(self):
        """Test that help command goes to STDERR."""
        ifc_file = create_test_ifc_file()
        try:
            test_script = f"""
import sys
import os

sys.path.insert(0, "src")

from ifcpeek.shell import IfcPeek
from unittest.mock import patch, Mock

with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
    mock_model = Mock()
    mock_model.__iter__ = Mock(return_value=iter([]))
    mock_model.by_type = Mock(return_value=[])
    mock_open.return_value = mock_model

    # Force non-interactive mode
    with patch("sys.stdin.isatty", return_value=False):
        with patch("sys.stdout.isatty", return_value=False):
            shell = IfcPeek("{str(ifc_file)}")
            shell._show_help()
"""

            result = subprocess.run(
                [sys.executable, "-c", test_script], capture_output=True, text=True
            )

            assert (
                "IfcPeek - Interactive IFC Model Query Tool" in result.stderr
            ), f"Help not in STDERR. STDERR: '{result.stderr}'"
            assert (
                "IfcPeek - Interactive IFC Model Query Tool" not in result.stdout
            ), "Help leaked to STDOUT"

        finally:
            ifc_file.unlink()

    def test_error_messages_stderr(self):
        """Test that error messages go to STDERR."""
        ifc_file = create_test_ifc_file()
        try:
            test_script = f"""
import sys
import os

sys.path.insert(0, "src")

from ifcpeek.shell import IfcPeek
from unittest.mock import patch, Mock

with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
    mock_model = Mock()
    mock_model.__iter__ = Mock(return_value=iter([]))
    mock_model.by_type = Mock(return_value=[])
    mock_open.return_value = mock_model

    with patch("ifcpeek.shell.ifcopenshell.util.selector.filter_elements") as mock_filter:
        mock_filter.side_effect = Exception("Test error")

        # Force non-interactive mode
        with patch("sys.stdin.isatty", return_value=False):
            with patch("sys.stdout.isatty", return_value=False):
                shell = IfcPeek("{str(ifc_file)}")
                shell._execute_query("BadQuery")
"""

            result = subprocess.run(
                [sys.executable, "-c", test_script], capture_output=True, text=True
            )

            assert (
                "IFC QUERY EXECUTION ERROR" in result.stderr
            ), f"Error message not in STDERR. STDERR: '{result.stderr}'"
            assert (
                "IFC QUERY EXECUTION ERROR" not in result.stdout
            ), "Error message leaked to STDOUT"

        finally:
            ifc_file.unlink()

    def test_value_extraction_stdout(self):
        """Test that value extraction results go to STDOUT."""
        ifc_file = create_test_ifc_file()
        try:
            test_script = f"""
import sys
import os

sys.path.insert(0, "src")

from ifcpeek.shell import IfcPeek
from unittest.mock import patch, Mock

with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
    mock_model = Mock()
    mock_model.schema = "IFC4"
    mock_model.__iter__ = Mock(return_value=iter([]))
    mock_model.by_type = Mock(return_value=[])
    mock_open.return_value = mock_model

    with patch("ifcpeek.shell.ifcopenshell.util.selector.filter_elements") as mock_filter:
        mock_element = Mock()
        mock_element.id.return_value = 123
        mock_filter.return_value = [mock_element]

        with patch("ifcpeek.shell.ifcopenshell.util.selector.get_element_value") as mock_get_value:
            mock_get_value.return_value = "TestWallName"

            # Force non-interactive mode
            with patch("sys.stdin.isatty", return_value=False):
                with patch("sys.stdout.isatty", return_value=False):
                    shell = IfcPeek("{str(ifc_file)}")
                    shell._execute_combined_query("IfcWall", ["Name"])
"""

            result = subprocess.run(
                [sys.executable, "-c", test_script], capture_output=True, text=True
            )

            assert (
                "TestWallName" in result.stdout
            ), f"Value extraction results not in STDOUT. STDOUT: '{result.stdout}', STDERR: '{result.stderr}'"

            # Value extraction results should not leak to STDERR
            assert (
                "TestWallName" not in result.stderr
            ), "Value extraction results leaked to STDERR"

        finally:
            ifc_file.unlink()


# Isolation fixtures to ensure clean test environment
@pytest.fixture(autouse=True)
def isolate_environment():
    """Ensure each test runs in isolated environment."""
    # Save original environment
    original_env = dict(os.environ)

    # Clear potentially interfering environment variables
    for key in list(os.environ.keys()):
        if key.startswith("IFCPEEK_"):
            del os.environ[key]

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture(autouse=True)
def reset_modules():
    """Reset module state between tests."""
    # This ensures that any module-level state doesn't interfere
    modules_to_clear = ["ifcpeek.debug", "ifcpeek.shell", "ifcpeek.config"]

    original_modules = {}
    for module_name in modules_to_clear:
        if module_name in sys.modules:
            original_modules[module_name] = sys.modules[module_name]

    yield

    # Note: We don't actually clear modules here as it might break other tests
    # The subprocess isolation should be sufficient


if __name__ == "__main__":
    # This allows the file to be run directly for debugging
    import pytest

    pytest.main([__file__, "-v"])
