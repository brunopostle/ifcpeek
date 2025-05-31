"""
Consolidated unit tests for IfcPeek value extraction functionality.
Tests query parsing, value extraction, output formatting, and integration.
"""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path
import tempfile
import os

from ifcpeek.shell import IfcPeek


@pytest.fixture
def shell_fixture():
    """Create a shell fixture for testing."""
    with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as tmp:
        tmp.write(b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;")
        tmp_path = tmp.name

    try:
        mock_model = Mock()
        mock_model.schema = "IFC4"

        with patch("ifcopenshell.open", return_value=mock_model):
            with patch("ifcpeek.shell.PromptSession"):
                with patch(
                    "ifcpeek.shell.get_history_file_path",
                    return_value=Path("/tmp/history"),
                ):
                    shell = IfcPeek(tmp_path)
                    shell.model = mock_model
                    return shell
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass


class TestQueryParsing:
    """Test query parsing functionality."""

    def test_parse_simple_query(self, shell_fixture):
        """Test parsing simple query without semicolons."""
        shell = shell_fixture
        filter_query, value_queries, is_combined = shell._parse_combined_query(
            "IfcWall"
        )

        assert filter_query == "IfcWall"
        assert value_queries == []
        assert is_combined is False

    def test_parse_combined_query_single_value(self, shell_fixture):
        """Test parsing combined query with single value extraction."""
        shell = shell_fixture
        filter_query, value_queries, is_combined = shell._parse_combined_query(
            "IfcWall ; Name"
        )

        assert filter_query == "IfcWall"
        assert value_queries == ["Name"]
        assert is_combined is True

    def test_parse_combined_query_multiple_values(self, shell_fixture):
        """Test parsing combined query with multiple value extractions."""
        shell = shell_fixture
        filter_query, value_queries, is_combined = shell._parse_combined_query(
            "IfcWall ; Name ; type.Name ; material.Name"
        )

        assert filter_query == "IfcWall"
        assert value_queries == ["Name", "type.Name", "material.Name"]
        assert is_combined is True

    def test_parse_query_empty_filter(self, shell_fixture):
        """Test parsing with empty filter query."""
        shell = shell_fixture
        with pytest.raises(ValueError, match="Filter query.*cannot be empty"):
            shell._parse_combined_query(" ; Name ; type.Name")

    def test_parse_whitespace_handling(self, shell_fixture):
        """Test whitespace handling in parsing."""
        shell = shell_fixture
        filter_query, value_queries, is_combined = shell._parse_combined_query(
            "  IfcWall  ;  Name  ;  type.Name  "
        )

        assert filter_query == "IfcWall"
        assert value_queries == ["Name", "type.Name"]
        assert is_combined is True


class TestInputProcessing:
    """Test input processing and routing logic."""

    def test_process_input_simple_query(self, shell_fixture):
        """Test processing simple query routes to _execute_query."""
        shell = shell_fixture

        with patch.object(shell, "_execute_query") as mock_execute:
            result = shell._process_input("IfcWall")

            mock_execute.assert_called_once_with("IfcWall")
            assert result is True

    def test_process_input_combined_query(self, shell_fixture):
        """Test processing combined query routes to _execute_combined_query."""
        shell = shell_fixture

        with patch.object(shell, "_execute_combined_query") as mock_execute_combined:
            result = shell._process_input("IfcWall ; Name")

            mock_execute_combined.assert_called_once_with("IfcWall", ["Name"])
            assert result is True

    def test_process_input_builtin_commands(self, shell_fixture):
        """Test that built-in commands still work."""
        shell = shell_fixture

        with patch.object(shell, "_show_help", return_value=True) as mock_help:
            result = shell._process_input("/help")

            mock_help.assert_called_once()
            assert result is True


class TestValueExtraction:
    """Test value extraction functionality."""

    def test_extract_simple_string_value(self, shell_fixture):
        """Test extracting simple string value."""
        shell = shell_fixture
        mock_element = Mock()
        mock_element.id.return_value = 123

        with patch(
            "ifcopenshell.util.selector.get_element_value", return_value="TestWall"
        ):
            result = shell.value_extractor.extract_element_value(mock_element, "Name")
            assert result == "TestWall"

    def test_extract_none_value(self, shell_fixture):
        """Test extracting None value returns empty string."""
        shell = shell_fixture
        mock_element = Mock()
        mock_element.id.return_value = 123

        with patch("ifcopenshell.util.selector.get_element_value", return_value=None):
            result = shell.value_extractor.extract_element_value(
                mock_element, "NonExistentProperty"
            )
            assert result == ""

    def test_extract_list_value(self, shell_fixture):
        """Test extracting list value returns placeholder."""
        shell = shell_fixture
        mock_element = Mock()
        mock_element.id.return_value = 123

        with patch(
            "ifcopenshell.util.selector.get_element_value",
            return_value=["item1", "item2", "item3"],
        ):
            result = shell.value_extractor.extract_element_value(
                mock_element, "ListProperty"
            )
            assert result == "<List[3]>"

    def test_extract_numeric_values(self, shell_fixture):
        """Test extracting numeric values."""
        shell = shell_fixture
        mock_element = Mock()
        mock_element.id.return_value = 123

        test_cases = [
            (42, "42"),
            (3.14159, "3.14159"),
            (True, "True"),
            (False, "False"),
        ]

        for input_value, expected_output in test_cases:
            with patch(
                "ifcopenshell.util.selector.get_element_value", return_value=input_value
            ):
                result = shell.value_extractor.extract_element_value(
                    mock_element, "TestProperty"
                )
                assert result == expected_output

    def test_extract_exception_handling(self, shell_fixture, capsys):
        """Test exception handling returns empty string and logs to STDERR."""
        shell = shell_fixture
        mock_element = Mock()
        mock_element.id.return_value = 123

        with patch(
            "ifcopenshell.util.selector.get_element_value",
            side_effect=Exception("Property not found"),
        ):
            result = shell.value_extractor.extract_element_value(
                mock_element, "BadProperty"
            )

            assert result == ""
            captured = capsys.readouterr()
            assert "Property 'BadProperty' not found on entity #123" in captured.err


class TestProcessValueQueries:
    """Test batch value processing."""

    def test_process_single_element_multiple_queries(self, shell_fixture):
        """Test processing single element with multiple value queries."""
        shell = shell_fixture

        mock_element = Mock()
        mock_element.id.return_value = 123
        elements = [mock_element]
        value_queries = ["Name", "type.Name", "material.Name"]

        def mock_extract_side_effect(element, query):
            value_map = {
                "Name": "TestWall",
                "type.Name": "WallType01",
                "material.Name": "Concrete",
            }
            return value_map.get(query, "")

        with patch.object(
            shell.value_extractor,
            "extract_element_value",
            side_effect=mock_extract_side_effect,
        ):
            results = shell.value_extractor.process_value_queries(
                elements, value_queries
            )

            assert len(results) == 1
            assert len(results[0]) == 3
            assert results[0] == ["TestWall", "WallType01", "Concrete"]

    def test_process_multiple_elements(self, shell_fixture):
        """Test processing multiple elements."""
        shell = shell_fixture

        mock_element1 = Mock()
        mock_element1.id.return_value = 123
        mock_element2 = Mock()
        mock_element2.id.return_value = 124
        elements = [mock_element1, mock_element2]
        value_queries = ["Name", "type.Name"]

        def mock_extract_side_effect(element, query):
            if element.id() == 123:
                return "Wall1" if query == "Name" else "Type1"
            else:
                return "Wall2" if query == "Name" else "Type2"

        with patch.object(
            shell.value_extractor,
            "extract_element_value",
            side_effect=mock_extract_side_effect,
        ):
            results = shell.value_extractor.process_value_queries(
                elements, value_queries
            )

            assert len(results) == 2
            assert results[0] == ["Wall1", "Type1"]
            assert results[1] == ["Wall2", "Type2"]

    def test_process_with_errors(self, shell_fixture, capsys):
        """Test processing continues even when some extractions fail."""
        shell = shell_fixture

        mock_element = Mock()
        mock_element.id.return_value = 123
        elements = [mock_element]
        value_queries = ["GoodProperty", "BadProperty"]

        def mock_extract_side_effect(element, query):
            if query == "GoodProperty":
                return "GoodValue"
            else:
                return ""  # extract_element_value handles errors internally

        with patch.object(
            shell.value_extractor,
            "extract_element_value",
            side_effect=mock_extract_side_effect,
        ):
            results = shell.value_extractor.process_value_queries(
                elements, value_queries
            )

            assert len(results) == 1
            assert results[0] == ["GoodValue", ""]


class TestOutputFormatting:
    """Test output formatting functionality."""

    def test_format_single_value(self, shell_fixture):
        """Test formatting single value (no tabs)."""
        shell = shell_fixture
        result = shell.value_extractor.format_value_output(["TestWall"])
        assert result == "TestWall"

    def test_format_multiple_values(self, shell_fixture):
        """Test formatting multiple values (tab-separated)."""
        shell = shell_fixture
        result = shell.value_extractor.format_value_output(
            ["TestWall", "WallType01", "Concrete"]
        )
        assert result == "TestWall\tWallType01\tConcrete"

    def test_format_values_with_tabs(self, shell_fixture):
        """Test formatting values containing tabs (should be replaced with spaces)."""
        shell = shell_fixture
        result = shell.value_extractor.format_value_output(["Test\tWall", "Type\t01"])
        assert result == "Test Wall\tType 01"


class TestCombinedQueryExecution:
    """Test combined query execution."""

    def test_execute_combined_query_no_results(self, shell_fixture, capsys):
        """Test combined query execution with no filter results."""
        shell = shell_fixture

        with patch("ifcopenshell.util.selector.filter_elements", return_value=[]):
            shell._execute_combined_query("IfcWall", ["Name"])

            captured = capsys.readouterr()
            assert captured.out == ""  # No output for no results

    def test_execute_combined_query_with_values(self, shell_fixture, capsys):
        """Test combined query execution with value queries."""
        shell = shell_fixture

        mock_element1 = Mock()
        mock_element1.id.return_value = 123
        mock_element2 = Mock()
        mock_element2.id.return_value = 124
        mock_elements = [mock_element1, mock_element2]

        def mock_extract_side_effect(element, query):
            if element.id() == 123:
                return "Wall1" if query == "Name" else "Type1"
            else:
                return "Wall2" if query == "Name" else "Type2"

        with patch(
            "ifcopenshell.util.selector.filter_elements", return_value=mock_elements
        ):
            with patch.object(
                shell.value_extractor,
                "extract_element_value",
                side_effect=mock_extract_side_effect,
            ):
                shell._execute_combined_query("IfcWall", ["Name", "type.Name"])

                captured = capsys.readouterr()
                output_lines = captured.out.strip().split("\n")

                assert len(output_lines) == 2
                assert output_lines[0] == "Wall1\tType1"
                assert output_lines[1] == "Wall2\tType2"

    def test_execute_combined_query_filter_error(self, shell_fixture, capsys):
        """Test combined query handles filter errors gracefully."""
        shell = shell_fixture

        with patch(
            "ifcopenshell.util.selector.filter_elements",
            side_effect=Exception("Invalid filter"),
        ):
            shell._execute_combined_query("BadFilter[", ["Name"])

            captured = capsys.readouterr()
            assert "IFC QUERY EXECUTION ERROR" in captured.err
            assert "Filter query: BadFilter[" in captured.err
            assert captured.out == ""  # No output on filter error


class TestEndToEndIntegration:
    """Test complete end-to-end integration scenarios."""

    def test_complete_workflow_single_value(self, shell_fixture, capsys):
        """Test complete workflow from input to output with single value."""
        shell = shell_fixture

        mock_element = Mock()
        mock_element.id.return_value = 123

        with patch(
            "ifcopenshell.util.selector.filter_elements", return_value=[mock_element]
        ):
            with patch(
                "ifcopenshell.util.selector.get_element_value", return_value="TestWall"
            ):
                result = shell._process_input("IfcWall ; Name")

                assert result is True
                captured = capsys.readouterr()
                assert captured.out.strip() == "TestWall"

    def test_complete_workflow_multiple_values(self, shell_fixture, capsys):
        """Test complete workflow with multiple values."""
        shell = shell_fixture

        mock_element1 = Mock()
        mock_element1.id.return_value = 123
        mock_element2 = Mock()
        mock_element2.id.return_value = 124
        elements = [mock_element1, mock_element2]

        def mock_get_value(element, query):
            element_id = element.id()
            if query == "Name":
                return f"Wall{element_id}"
            elif query == "type.Name":
                return f"Type{element_id}"
            else:
                return f"Material{element_id}"

        with patch("ifcopenshell.util.selector.filter_elements", return_value=elements):
            with patch(
                "ifcopenshell.util.selector.get_element_value",
                side_effect=mock_get_value,
            ):
                result = shell._process_input(
                    "IfcWall ; Name ; type.Name ; material.Name"
                )

                assert result is True
                captured = capsys.readouterr()
                output_lines = captured.out.strip().split("\n")

                assert len(output_lines) == 2
                assert output_lines[0] == "Wall123\tType123\tMaterial123"
                assert output_lines[1] == "Wall124\tType124\tMaterial124"

    def test_backwards_compatibility_simple_queries(self, shell_fixture, capsys):
        """Test that simple queries still work unchanged."""
        shell = shell_fixture

        mock_element = Mock()
        mock_element.__str__ = Mock(
            return_value="#123=IFCWALL('guid',$,$,'Wall',$,$,$,$,$);"
        )

        with patch(
            "ifcopenshell.util.selector.filter_elements", return_value=[mock_element]
        ):
            with patch(
                "ifcpeek.shell.format_query_results", return_value=["#123=IFCWALL"]
            ):
                result = shell._process_input("IfcWall")

                assert result is True
                captured = capsys.readouterr()
                assert "#123=IFCWALL" in captured.out


class TestCommonIfcProperties:
    """Test extraction of common IFC properties."""

    def test_common_ifc_property_patterns(self, shell_fixture):
        """Test extraction of common IFC property patterns."""
        shell = shell_fixture
        mock_element = Mock()
        mock_element.id.return_value = 123

        # Test common IFC property patterns
        common_properties = [
            ("Name", "TestWall"),
            ("type.Name", "BasicWall"),
            ("material.Name", "Concrete"),
            ("Pset_WallCommon.IsExternal", "True"),
            ("Pset_WallCommon.FireRating", "2HR"),
            ("storey.Name", "Level 1"),
            ("Qto_WallBaseQuantities.Length", "5.0"),
        ]

        for property_name, expected_value in common_properties:
            with patch(
                "ifcopenshell.util.selector.get_element_value",
                return_value=expected_value,
            ):
                result = shell.value_extractor.extract_element_value(
                    mock_element, property_name
                )
                assert result == expected_value


class TestErrorHandling:
    """Test comprehensive error handling."""

    def test_no_shell_crash_on_errors(self, shell_fixture):
        """Test that the shell never crashes due to value extraction errors."""
        shell = shell_fixture

        mock_element = Mock()
        mock_element.id.return_value = 123

        exception_types = [
            Exception("Generic error"),
            ValueError("Value error"),
            AttributeError("Attribute error"),
            RuntimeError("Runtime error"),
        ]

        for exception in exception_types:
            with patch(
                "ifcopenshell.util.selector.get_element_value", side_effect=exception
            ):
                # Should not raise any exceptions
                result = shell.value_extractor.extract_element_value(
                    mock_element, "BadProperty"
                )
                assert result == ""

    def test_stderr_message_format(self, shell_fixture, capsys):
        """Test that STDERR messages follow the specified format."""
        shell = shell_fixture
        mock_element = Mock()
        mock_element.id.return_value = 123

        with patch(
            "ifcopenshell.util.selector.get_element_value",
            side_effect=Exception("Property not found"),
        ):
            result = shell.value_extractor.extract_element_value(
                mock_element, "BadProperty"
            )

            assert result == ""
            captured = capsys.readouterr()
            assert "Property 'BadProperty' not found on entity #123" in captured.err


if __name__ == "__main__":
    print("IfcPeek Value Extraction - Consolidated Test Suite")
    print("=" * 55)
    print("Testing:")
    print("  • Query parsing and routing")
    print("  • Value extraction engine")
    print("  • Output formatting")
    print("  • Combined query execution")
    print("  • End-to-end integration")
    print("  • Error handling")
    print("  • Backwards compatibility")
    print("=" * 55)

    pytest.main([__file__, "-v", "--tb=short"])
