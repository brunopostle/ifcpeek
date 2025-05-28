"""
Comprehensive test to validate the complete IFC query execution workflow.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch, Mock
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr

# Import our shell module
from ifcpeek.shell import IfcPeek


class TestCompleteQueryWorkflow:
    """Test the complete query execution workflow."""

    def create_test_ifc_file(self):
        """Create a temporary IFC file for testing."""
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
#7=IFCWALL('wall-guid-001',$,$,'TestWall-001',$,$,$,$,$);
#8=IFCWALL('wall-guid-002',$,$,'TestWall-002',$,$,$,$,$);
#9=IFCDOOR('door-guid-001',$,$,'TestDoor-001',$,$,$,$,$);
ENDSEC;
END-ISO-10303-21;"""

        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".ifc", delete=False)
        temp_file.write(ifc_content)
        temp_file.close()
        return Path(temp_file.name)

    def test_successful_query_execution(self):
        """Test successful query execution with results."""
        ifc_file = self.create_test_ifc_file()

        try:
            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_model.schema = "IFC4"
                mock_open.return_value = mock_model

                # Mock the selector module at the shell module level
                with patch(
                    "ifcpeek.shell.ifcopenshell.util.selector.filter_elements"
                ) as mock_filter:
                    shell = IfcPeek(str(ifc_file))

                    # Create mock entities with realistic SPF representations
                    mock_wall1 = Mock()
                    mock_wall1.__str__ = Mock(
                        return_value="#7=IFCWALL('wall-guid-001',$,$,'TestWall-001',$,$,$,$,$);"
                    )

                    mock_wall2 = Mock()
                    mock_wall2.__str__ = Mock(
                        return_value="#8=IFCWALL('wall-guid-002',$,$,'TestWall-002',$,$,$,$,$);"
                    )

                    mock_filter.return_value = [mock_wall1, mock_wall2]

                    # Capture output
                    output = StringIO()
                    with redirect_stdout(output):
                        shell._execute_query("IfcWall")

                    result = output.getvalue()
                    lines = result.strip().split("\n")

                    # Verify results
                    assert len(lines) == 2
                    assert "#7=IFCWALL('wall-guid-001'" in lines[0]
                    assert "#8=IFCWALL('wall-guid-002'" in lines[1]

                    # Verify selector was called correctly
                    mock_filter.assert_called_once_with(mock_model, "IfcWall")

        finally:
            ifc_file.unlink()

    def test_empty_query_results(self):
        """Test query execution with empty results."""
        ifc_file = self.create_test_ifc_file()

        try:
            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_model.schema = "IFC4"
                mock_open.return_value = mock_model

                with patch(
                    "ifcpeek.shell.ifcopenshell.util.selector.filter_elements"
                ) as mock_filter:
                    shell = IfcPeek(str(ifc_file))

                    mock_filter.return_value = []  # Empty results

                    # Capture output
                    output = StringIO()
                    with redirect_stdout(output):
                        shell._execute_query("IfcNonExistentType")

                    result = output.getvalue()

                    # Empty results should produce no output
                    assert result == ""

        finally:
            ifc_file.unlink()

    def test_query_syntax_error_handling(self):
        """Test handling of query syntax errors."""
        ifc_file = self.create_test_ifc_file()

        try:
            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_model.schema = "IFC4"
                mock_open.return_value = mock_model

                with patch(
                    "ifcpeek.shell.ifcopenshell.util.selector.filter_elements"
                ) as mock_filter:
                    shell = IfcPeek(str(ifc_file))

                    mock_filter.side_effect = SyntaxError("Invalid selector syntax")

                    # Capture output
                    output = StringIO()
                    with redirect_stderr(output):
                        shell._execute_query("Invalid[Query")

                    result = output.getvalue()

                    # Should contain error information
                    assert "IFC QUERY EXECUTION ERROR" in result
                    assert "Query: Invalid[Query" in result
                    assert "SyntaxError: Invalid selector syntax" in result
                    assert "FULL PYTHON TRACEBACK:" in result

        finally:
            ifc_file.unlink()

    def test_input_processing_routes_to_query_execution(self):
        """Test that input processing correctly routes queries to execution."""
        ifc_file = self.create_test_ifc_file()

        try:
            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_model.schema = "IFC4"
                mock_open.return_value = mock_model

                shell = IfcPeek(str(ifc_file))

                # Mock _execute_query to verify it's called
                with patch.object(shell, "_execute_query") as mock_execute:
                    result = shell._process_input("IfcWall, Name=TestWall")

                    assert result is True  # Should continue shell
                    mock_execute.assert_called_once_with("IfcWall, Name=TestWall")

        finally:
            ifc_file.unlink()

    def test_commands_bypass_query_execution(self):
        """Test that built-in commands bypass query execution."""
        ifc_file = self.create_test_ifc_file()

        try:
            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_model.schema = "IFC4"
                mock_open.return_value = mock_model

                shell = IfcPeek(str(ifc_file))

                # Mock _execute_query to verify it's NOT called
                with patch.object(shell, "_execute_query") as mock_execute:
                    # Test various commands
                    result1 = shell._process_input("/help")
                    result2 = shell._process_input("/exit")
                    result3 = shell._process_input("/quit")

                    assert result1 is True  # Help continues
                    assert result2 is False  # Exit terminates
                    assert result3 is False  # Quit terminates

                    # _execute_query should never be called
                    mock_execute.assert_not_called()

        finally:
            ifc_file.unlink()

    def test_complex_query_scenarios(self):
        """Test complex query scenarios."""
        ifc_file = self.create_test_ifc_file()

        try:
            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_model.schema = "IFC4"
                mock_open.return_value = mock_model

                with patch(
                    "ifcpeek.shell.ifcopenshell.util.selector.filter_elements"
                ) as mock_filter:
                    shell = IfcPeek(str(ifc_file))

                    # Test various complex queries
                    complex_queries = [
                        "IfcWall, material=concrete",
                        "IfcElement, Name=Door-01",
                        "IfcBuildingElement, type=wall, height>3.0",
                        "IfcWall | IfcDoor",
                        "IfcSpace, Name~office",
                    ]

                    mock_entity = Mock()
                    mock_entity.__str__ = Mock(
                        return_value="#100=IFCELEMENT('guid',$,$,'Element',$,$,$,$,$);"
                    )

                    for query in complex_queries:
                        mock_filter.return_value = [mock_entity]

                        # Capture output
                        output = StringIO()
                        with redirect_stdout(output):
                            shell._execute_query(query)

                        result = output.getvalue().strip()

                        # Should contain the entity SPF format
                        assert "#100=IFCELEMENT('guid'" in result

                        # Verify correct query was passed to filter_elements
                        mock_filter.assert_called_with(mock_model, query)

        finally:
            ifc_file.unlink()

    def test_shell_continues_after_query_errors(self):
        """Test that shell continues operating after query errors."""
        ifc_file = self.create_test_ifc_file()

        try:
            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_model.schema = "IFC4"
                mock_open.return_value = mock_model

                with patch(
                    "ifcpeek.shell.ifcopenshell.util.selector.filter_elements"
                ) as mock_filter:
                    shell = IfcPeek(str(ifc_file))

                    # First call raises error, second call succeeds
                    mock_entity = Mock()
                    mock_entity.__str__ = Mock(
                        return_value="#200=IFCDOOR('door-guid',$,$,'Door',$,$,$,$,$);"
                    )

                    mock_filter.side_effect = [
                        SyntaxError("Invalid selector syntax"),
                        [mock_entity],
                    ]

                    # Test error recovery
                    output1 = StringIO()
                    with redirect_stderr(output1):
                        result1 = shell._process_input("Invalid[Query")

                    assert result1 is True  # Should continue despite error
                    error_output = output1.getvalue()
                    assert "IFC QUERY EXECUTION ERROR" in error_output

                    # Test successful query after error
                    output2 = StringIO()
                    with redirect_stdout(output2):
                        result2 = shell._process_input("IfcDoor")

                    assert result2 is True  # Should continue
                    success_output = output2.getvalue()
                    assert "#200=IFCDOOR('door-guid'" in success_output

        finally:
            ifc_file.unlink()


def run_comprehensive_tests():
    """Run all comprehensive tests."""
    print("Running comprehensive IFC query execution tests...")
    print("=" * 60)

    test_suite = TestCompleteQueryWorkflow()

    tests = [
        ("Successful Query Execution", test_suite.test_successful_query_execution),
        ("Empty Query Results", test_suite.test_empty_query_results),
        ("Query Syntax Error Handling", test_suite.test_query_syntax_error_handling),
        (
            "Input Processing Routes to Query",
            test_suite.test_input_processing_routes_to_query_execution,
        ),
        (
            "Commands Bypass Query Execution",
            test_suite.test_commands_bypass_query_execution,
        ),
        ("Complex Query Scenarios", test_suite.test_complex_query_scenarios),
        (
            "Shell Continues After Errors",
            test_suite.test_shell_continues_after_query_errors,
        ),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            print(f"Running: {test_name}...")
            test_func()
            print(f"✓ {test_name} - PASSED")
            passed += 1
        except Exception as e:
            print(f"✗ {test_name} - FAILED: {e}")
            import traceback

            traceback.print_exc()
            failed += 1

    print("=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 All tests passed successfully!")
        return True
    else:
        print("❌ Some tests failed.")
        return False


if __name__ == "__main__":
    success = run_comprehensive_tests()
    exit(0 if success else 1)
