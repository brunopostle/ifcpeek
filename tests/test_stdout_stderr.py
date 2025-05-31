"""
test_stdout_stderr.py - Focused STDOUT/STDERR separation tests
"""

import tempfile
import subprocess
import sys
import os
from pathlib import Path

os.environ["IFCPEEK_DEBUG"] = "1"


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


def test_query_results_stdout():
    """Test that query results go to STDOUT, debug messages to STDERR."""
    ifc_file = create_test_ifc_file()
    try:
        test_script = f"""
import sys
sys.path.insert(0, 'src')
from ifcpeek.shell import IfcPeek
from unittest.mock import patch, Mock

# Mock dependencies
with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
    mock_model = Mock()
    mock_model.schema = "IFC4"
    mock_open.return_value = mock_model
    
    with patch("ifcpeek.shell.ifcopenshell.util.selector.filter_elements") as mock_filter:
        mock_wall = Mock()
        mock_wall.__str__ = Mock(return_value="#7=IFCWALL('wall-guid-001',$,$,'TestWall-001',$,$,$,$,$);")
        mock_filter.return_value = [mock_wall]
        
        shell = IfcPeek("{str(ifc_file)}")
        shell._execute_query("IfcWall")
"""

        result = subprocess.run(
            [sys.executable, "-c", test_script], capture_output=True, text=True
        )

        # Results should be in STDOUT
        assert (
            "#7=IFCWALL('wall-guid-001'" in result.stdout
        ), "Query results not in STDOUT"
        # Debug info should be in STDERR
        assert "DEBUG:" in result.stderr, "Debug messages not in STDERR"
        # No results should leak to STDERR
        assert (
            "#7=IFCWALL('wall-guid-001'" not in result.stderr
        ), "Query results leaked to STDERR"

    finally:
        ifc_file.unlink()


def test_help_command_stderr():
    """Test that help command goes to STDERR."""
    ifc_file = create_test_ifc_file()
    try:
        test_script = f"""
import sys
sys.path.insert(0, 'src')
from ifcpeek.shell import IfcPeek
from unittest.mock import patch, Mock

with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
    mock_model = Mock()
    mock_open.return_value = mock_model
    
    shell = IfcPeek("{str(ifc_file)}")
    shell._show_help()
"""

        result = subprocess.run(
            [sys.executable, "-c", test_script], capture_output=True, text=True
        )

        assert (
            "IfcPeek - Interactive IFC Model Query Tool" in result.stderr
        ), "Help not in STDERR"
        assert (
            "IfcPeek - Interactive IFC Model Query Tool" not in result.stdout
        ), "Help leaked to STDOUT"

    finally:
        ifc_file.unlink()


def test_error_messages_stderr():
    """Test that error messages go to STDERR."""
    ifc_file = create_test_ifc_file()
    try:
        test_script = f"""
import sys
sys.path.insert(0, 'src')
from ifcpeek.shell import IfcPeek
from unittest.mock import patch, Mock

with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
    mock_model = Mock()
    mock_open.return_value = mock_model
    
    with patch("ifcpeek.shell.ifcopenshell.util.selector.filter_elements") as mock_filter:
        mock_filter.side_effect = Exception("Test error")
        
        shell = IfcPeek("{str(ifc_file)}")
        shell._execute_query("BadQuery")
"""

        result = subprocess.run(
            [sys.executable, "-c", test_script], capture_output=True, text=True
        )

        assert (
            "IFC QUERY EXECUTION ERROR" in result.stderr
        ), "Error message not in STDERR"
        assert (
            "IFC QUERY EXECUTION ERROR" not in result.stdout
        ), "Error message leaked to STDOUT"

    finally:
        ifc_file.unlink()


def test_empty_results():
    """Test that empty query results produce no STDOUT output."""
    ifc_file = create_test_ifc_file()
    try:
        test_script = f"""
import sys
sys.path.insert(0, 'src')
from ifcpeek.shell import IfcPeek
from unittest.mock import patch, Mock

with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
    mock_model = Mock()
    mock_open.return_value = mock_model
    
    with patch("ifcpeek.shell.ifcopenshell.util.selector.filter_elements") as mock_filter:
        mock_filter.return_value = []  # Empty results
        
        shell = IfcPeek("{str(ifc_file)}")
        shell._execute_query("IfcNonExistent")
"""

        result = subprocess.run(
            [sys.executable, "-c", test_script], capture_output=True, text=True
        )

        assert (
            len(result.stdout.strip()) == 0
        ), "STDOUT should be empty for empty results"
        assert "DEBUG:" in result.stderr, "Debug messages should still appear in STDERR"

    finally:
        ifc_file.unlink()


# Remove the main() function and standalone test functions
# since pytest will discover and run the test_ functions automatically

if __name__ == "__main__":
    # This allows the file to be run directly for debugging
    import pytest

    pytest.main([__file__])
