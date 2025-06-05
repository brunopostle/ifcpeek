"""
Minimal focused test suite for ifcpeek core functionality.
"""

from unittest.mock import Mock, patch

from ifcpeek.shell import IfcPeek
from ifcpeek.formatters import StepHighlighter, format_query_results


class TestBasicShellFunctionality:
    """Test essential shell functionality without conflicts."""

    def test_builtin_commands_work(self, mock_ifc_file):
        """Test that built-in commands function correctly."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Help should return True (continue shell)
            assert shell._process_input("/help") is True

            # Exit commands should return False (terminate shell)
            assert shell._process_input("/exit") is False
            assert shell._process_input("/quit") is False

    def test_query_routing_works(self, mock_ifc_file, mock_selector):
        """Test that queries are routed to execution correctly."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            with patch.object(shell, "_execute_query") as mock_execute:
                # Regular query should call _execute_query
                assert shell._process_input("IfcWall") is True
                mock_execute.assert_called_once_with("IfcWall")

                # Commands should not call _execute_query
                mock_execute.reset_mock()
                shell._process_input("/help")
                mock_execute.assert_not_called()

    def test_successful_query_produces_output(
        self, mock_ifc_file, mock_selector, capsys
    ):
        """Test successful query execution produces expected output."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Mock a wall entity
            mock_wall = Mock()
            mock_wall.__str__ = Mock(
                return_value="#7=IFCWALL('wall-guid-001',$,$,'TestWall-001');"
            )
            mock_selector.return_value = [mock_wall]

            shell._execute_query("IfcWall")

            captured = capsys.readouterr()
            # Should have wall entity in output
            assert "#7=IFCWALL('wall-guid-001'" in captured.out

    def test_empty_query_produces_no_output(self, mock_ifc_file, mock_selector, capsys):
        """Test empty query results produce no output."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))
            mock_selector.return_value = []

            shell._execute_query("IfcNonExistent")

            captured = capsys.readouterr()
            # Should have no output for empty results
            assert captured.out == ""

    def test_query_errors_are_handled(self, mock_ifc_file, mock_selector, capsys):
        """Test query errors are handled gracefully."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))
            mock_selector.side_effect = SyntaxError("Invalid selector syntax")

            shell._execute_query("Invalid[Query")

            captured = capsys.readouterr()
            # Should have error information in stderr
            assert "IFC QUERY EXECUTION ERROR" in captured.err
            assert "Invalid[Query" in captured.err


class TestFormatters:
    """Test formatting functionality without conflicts."""

    def test_step_highlighter_basic_functionality(self):
        """Test basic step highlighter functionality."""
        highlighter = StepHighlighter()

        line = "#1=IFCWALL('guid',$,$,'Wall');"
        result = highlighter.highlight_step_line(line)

        # Should return a string containing the entity
        assert isinstance(result, str)
        assert "IFCWALL" in result

    def test_format_query_results_basic(self):
        """Test basic result formatting functionality."""
        mock_entity = Mock()
        mock_entity.__str__ = Mock(return_value="#1=IFCWALL('guid');")

        results = list(format_query_results([mock_entity], enable_highlighting=False))

        assert len(results) == 1
        assert "#1=IFCWALL('guid')" in results[0]

    def test_format_handles_errors_gracefully(self, capsys):
        """Test formatting handles entity errors gracefully."""
        mock_entity = Mock()
        mock_entity.__str__ = Mock(side_effect=RuntimeError("Conversion failed"))

        results = list(format_query_results([mock_entity], enable_highlighting=False))

        assert len(results) == 1
        assert "Entity formatting error" in results[0]

        captured = capsys.readouterr()
        assert "ERROR: Failed to format entity" in captured.err


class TestEdgeCases:
    """Test edge cases that might cause issues."""

    def test_empty_input_handling(self, mock_ifc_file):
        """Test empty input is handled correctly."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Empty input should continue shell without calling query execution
            with patch.object(shell, "_execute_query") as mock_execute:
                assert shell._process_input("") is True
                assert shell._process_input("   ") is True
                mock_execute.assert_not_called()

    def test_whitespace_trimming(self, mock_ifc_file):
        """Test whitespace in queries is handled correctly."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            with patch.object(shell, "_execute_query") as mock_execute:
                shell._process_input("  IfcWall  ")
                # Should call with trimmed query
                mock_execute.assert_called_once_with("IfcWall")

    def test_shell_continues_after_errors(self, mock_ifc_file, mock_selector):
        """Test shell continues operating after query errors."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Error should not stop shell
            mock_selector.side_effect = SyntaxError("Bad query")
            assert shell._process_input("BadQuery") is True

            # Subsequent good query should work
            mock_selector.side_effect = None
            mock_selector.return_value = []
            assert shell._process_input("IfcWall") is True


class TestIntegration:
    """Basic integration test without complex setup."""

    def test_end_to_end_workflow(self, mock_ifc_file, mock_selector, capsys):
        """Test complete workflow works end-to-end."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            # Setup mocks
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            mock_entity = Mock()
            mock_entity.__str__ = Mock(return_value="#1=IFCWALL('guid',$,$,'Wall');")
            mock_selector.return_value = [mock_entity]

            # Initialize shell and execute query
            shell = IfcPeek(str(mock_ifc_file))

            # Clear any initialization output
            capsys.readouterr()

            # Execute query
            result = shell._process_input("IfcWall")

            # Verify results
            assert result is True
            captured = capsys.readouterr()
            assert "#1=IFCWALL('guid'" in captured.out


if __name__ == "__main__":
    # Simple smoke test
    print("Running minimal ifcpeek tests...")

    # Test basic functionality
    highlighter = StepHighlighter()
    test_line = "#1=IFCWALL('guid',$,$,'Wall');"
    result = highlighter.highlight_step_line(test_line)
    assert isinstance(result, str)

    print("✅ Basic functionality test passed")
    print("🎉 Smoke test completed successfully!")
