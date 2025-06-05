"""Simplified value extraction tests using centralized utilities."""

import pytest
from unittest.mock import patch

# Handle imports robustly
try:
    from .test_utils import (
        ShellTestBase,
        ValueExtractionTestMixin,
        MockSetup,
        assert_query_output_contains,
        assert_error_output_contains,
    )
except ImportError:
    from test_utils import (
        ShellTestBase,
        ValueExtractionTestMixin,
        MockSetup,
        assert_error_output_contains,
    )


class TestValueExtractionParsing(ShellTestBase):
    """Test value extraction query parsing with simplified setup."""

    def test_parse_simple_query(self, shell_with_mocks):
        """Test parsing simple query without semicolons."""
        (
            filter_query,
            value_queries,
            is_combined,
        ) = shell_with_mocks._parse_combined_query("IfcWall")

        assert filter_query == "IfcWall"
        assert value_queries == []
        assert is_combined is False

    def test_parse_combined_query_single_value(self, shell_with_mocks):
        """Test parsing combined query with single value extraction."""
        (
            filter_query,
            value_queries,
            is_combined,
        ) = shell_with_mocks._parse_combined_query("IfcWall ; Name")

        assert filter_query == "IfcWall"
        assert value_queries == ["Name"]
        assert is_combined is True

    def test_parse_combined_query_multiple_values(self, shell_with_mocks):
        """Test parsing combined query with multiple value extractions."""
        (
            filter_query,
            value_queries,
            is_combined,
        ) = shell_with_mocks._parse_combined_query(
            "IfcWall ; Name ; type.Name ; material.Name"
        )

        assert filter_query == "IfcWall"
        assert value_queries == ["Name", "type.Name", "material.Name"]
        assert is_combined is True

    def test_parse_query_empty_filter(self, shell_with_mocks):
        """Test parsing with empty filter query."""
        with pytest.raises(ValueError, match="Filter query.*cannot be empty"):
            shell_with_mocks._parse_combined_query(" ; Name ; type.Name")


class TestValueExtraction(ShellTestBase, ValueExtractionTestMixin):
    """Test value extraction functionality with simplified setup."""

    def test_extract_simple_string_value(self, shell_with_mocks):
        """Test extracting simple string value."""
        mock_element = MockSetup.create_mock_wall_entity()

        with patch(
            "ifcopenshell.util.selector.get_element_value", return_value="TestWall"
        ):
            result = shell_with_mocks.value_extractor.extract_element_value(
                mock_element, "Name"
            )
            assert result == "TestWall"

    def test_extract_none_value(self, shell_with_mocks):
        """Test extracting None value returns empty string."""
        mock_element = MockSetup.create_mock_wall_entity()

        with patch("ifcopenshell.util.selector.get_element_value", return_value=None):
            result = shell_with_mocks.value_extractor.extract_element_value(
                mock_element, "NonExistent"
            )
            assert result == ""

    def test_extract_list_value(self, shell_with_mocks):
        """Test extracting list value returns placeholder."""
        mock_element = MockSetup.create_mock_wall_entity()

        with patch(
            "ifcopenshell.util.selector.get_element_value",
            return_value=["item1", "item2", "item3"],
        ):
            result = shell_with_mocks.value_extractor.extract_element_value(
                mock_element, "ListProperty"
            )
            assert result == "<List[3]>"

    def test_extract_numeric_values(self, shell_with_mocks):
        """Test extracting numeric values."""
        mock_element = MockSetup.create_mock_wall_entity()

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
                result = shell_with_mocks.value_extractor.extract_element_value(
                    mock_element, "TestProperty"
                )
                assert result == expected_output

    def test_extract_exception_handling(self, shell_with_mocks, capsys):
        """Test exception handling returns empty string and logs to STDERR."""
        mock_element = MockSetup.create_mock_wall_entity()

        with patch(
            "ifcopenshell.util.selector.get_element_value",
            side_effect=Exception("Property not found"),
        ):
            result = shell_with_mocks.value_extractor.extract_element_value(
                mock_element, "BadProperty"
            )

            assert result == ""
            assert_error_output_contains(
                capsys, "Property 'BadProperty' not found on entity #1"
            )


class TestValueBatchProcessing(ShellTestBase, ValueExtractionTestMixin):
    """Test batch value processing with simplified setup."""

    def test_process_single_element_multiple_queries(self, shell_with_mocks):
        """Test processing single element with multiple value queries."""
        mock_element = MockSetup.create_mock_wall_entity()
        elements = [mock_element]
        value_queries = ["Name", "type.Name", "material.Name"]

        value_map = {
            "Name": "TestWall",
            "type.Name": "WallType01",
            "material.Name": "Concrete",
        }

        with patch.object(
            shell_with_mocks.value_extractor, "extract_element_value"
        ) as mock_extract:
            mock_extract.side_effect = lambda e, q: value_map.get(q, "")

            results = shell_with_mocks.value_extractor.process_value_queries(
                elements, value_queries
            )

            assert len(results) == 1
            assert len(results[0]) == 3
            assert results[0] == ["TestWall", "WallType01", "Concrete"]

    def test_process_multiple_elements(self, shell_with_mocks):
        """Test processing multiple elements."""
        mock_element1 = MockSetup.create_mock_wall_entity(wall_id=123, name="Wall1")
        mock_element2 = MockSetup.create_mock_wall_entity(wall_id=124, name="Wall2")
        elements = [mock_element1, mock_element2]
        value_queries = ["Name", "type.Name"]

        def mock_extract_side_effect(element, query):
            if element.id() == 123:
                return "Wall1" if query == "Name" else "Type1"
            else:
                return "Wall2" if query == "Name" else "Type2"

        with patch.object(
            shell_with_mocks.value_extractor,
            "extract_element_value",
            side_effect=mock_extract_side_effect,
        ):
            results = shell_with_mocks.value_extractor.process_value_queries(
                elements, value_queries
            )

            assert len(results) == 2
            assert results[0] == ["Wall1", "Type1"]
            assert results[1] == ["Wall2", "Type2"]


class TestOutputFormatting(ShellTestBase):
    """Test output formatting with simplified setup."""

    def test_format_single_value(self, shell_with_mocks):
        """Test formatting single value (no tabs)."""
        result = shell_with_mocks.value_extractor.format_value_output(["TestWall"])
        assert result == "TestWall"

    def test_format_multiple_values(self, shell_with_mocks):
        """Test formatting multiple values (tab-separated)."""
        result = shell_with_mocks.value_extractor.format_value_output(
            ["TestWall", "WallType01", "Concrete"]
        )
        assert result == "TestWall\tWallType01\tConcrete"

    def test_format_values_with_tabs(self, shell_with_mocks):
        """Test formatting values containing tabs (should be replaced with spaces)."""
        result = shell_with_mocks.value_extractor.format_value_output(
            ["Test\tWall", "Type\t01"]
        )
        assert result == "Test Wall\tType 01"


class TestCombinedQueryExecution(ShellTestBase, ValueExtractionTestMixin):
    """Test combined query execution with simplified setup."""

    def test_execute_combined_query_no_results(
        self, shell_with_mocks, mock_selector, capsys
    ):
        """Test combined query execution with no filter results."""
        mock_selector.return_value = []

        shell_with_mocks._execute_combined_query("IfcWall", ["Name"])

        captured = capsys.readouterr()
        assert captured.out == ""  # No output for no results

    def test_execute_combined_query_with_values(
        self, shell_with_mocks, mock_selector, capsys
    ):
        """Test combined query execution with value queries."""
        mock_element1 = MockSetup.create_mock_wall_entity(wall_id=123, name="Wall1")
        mock_element2 = MockSetup.create_mock_wall_entity(wall_id=124, name="Wall2")
        mock_elements = [mock_element1, mock_element2]

        def mock_extract_side_effect(element, query):
            if element.id() == 123:
                return "Wall1" if query == "Name" else "Type1"
            else:
                return "Wall2" if query == "Name" else "Type2"

        mock_selector.return_value = mock_elements

        with patch.object(
            shell_with_mocks.value_extractor,
            "extract_element_value",
            side_effect=mock_extract_side_effect,
        ):
            shell_with_mocks._execute_combined_query("IfcWall", ["Name", "type.Name"])

            captured = capsys.readouterr()
            output_lines = captured.out.strip().split("\n")

            assert len(output_lines) == 2
            assert output_lines[0] == "Wall1\tType1"
            assert output_lines[1] == "Wall2\tType2"

    def test_execute_combined_query_filter_error(
        self, shell_with_mocks, mock_selector, capsys
    ):
        """Test combined query handles filter errors gracefully."""
        mock_selector.side_effect = Exception("Invalid filter")

        shell_with_mocks._execute_combined_query("BadFilter[", ["Name"])

        captured = capsys.readouterr()
        assert "COMBINED QUERY EXECUTION ERROR" in captured.err
        assert "Filter query: BadFilter[" in captured.err
        assert captured.out == ""  # No output on filter error


class TestEndToEndIntegration(ShellTestBase, ValueExtractionTestMixin):
    """Test complete end-to-end integration scenarios with simplified setup."""

    def test_complete_workflow_single_value(
        self, shell_with_mocks, mock_selector, capsys
    ):
        """Test complete workflow from input to output with single value."""
        mock_element = MockSetup.create_mock_wall_entity()
        mock_selector.return_value = [mock_element]

        with patch(
            "ifcopenshell.util.selector.get_element_value", return_value="TestWall"
        ):
            result = shell_with_mocks._process_input("IfcWall ; Name")

            assert result is True
            captured = capsys.readouterr()
            assert captured.out.strip() == "TestWall"

    def test_complete_workflow_multiple_values(
        self, shell_with_mocks, mock_selector, capsys
    ):
        """Test complete workflow with multiple values."""
        elements = [
            MockSetup.create_mock_wall_entity(wall_id=123, name="Wall123"),
            MockSetup.create_mock_wall_entity(wall_id=124, name="Wall124"),
        ]
        mock_selector.return_value = elements

        def mock_get_value(element, query):
            element_id = element.id()
            if query == "Name":
                return f"Wall{element_id}"
            elif query == "type.Name":
                return f"Type{element_id}"
            else:
                return f"Material{element_id}"

        with patch(
            "ifcopenshell.util.selector.get_element_value", side_effect=mock_get_value
        ):
            result = shell_with_mocks._process_input(
                "IfcWall ; Name ; type.Name ; material.Name"
            )

            assert result is True
            captured = capsys.readouterr()
            output_lines = captured.out.strip().split("\n")

            assert len(output_lines) == 2
            assert output_lines[0] == "Wall123\tType123\tMaterial123"
            assert output_lines[1] == "Wall124\tType124\tMaterial124"

    def test_backwards_compatibility_simple_queries(
        self, shell_with_mocks, mock_selector, capsys
    ):
        """Test that simple queries still work unchanged."""
        mock_element = MockSetup.create_mock_wall_entity()
        mock_selector.return_value = [mock_element]

        with patch("ifcpeek.shell.format_query_results", return_value=["#1=IFCWALL"]):
            result = shell_with_mocks._process_input("IfcWall")

            assert result is True
            captured = capsys.readouterr()
            assert "#1=IFCWALL" in captured.out


class TestCommonIfcProperties(ShellTestBase):
    """Test extraction of common IFC properties with simplified setup."""

    def test_common_ifc_property_patterns(self, shell_with_mocks):
        """Test extraction of common IFC property patterns."""
        mock_element = MockSetup.create_mock_wall_entity()

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
                result = shell_with_mocks.value_extractor.extract_element_value(
                    mock_element, property_name
                )
                assert result == expected_value


class TestErrorHandling(ShellTestBase):
    """Test comprehensive error handling with simplified setup."""

    def test_no_shell_crash_on_errors(self, shell_with_mocks):
        """Test that the shell never crashes due to value extraction errors."""
        mock_element = MockSetup.create_mock_wall_entity()

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
                result = shell_with_mocks.value_extractor.extract_element_value(
                    mock_element, "BadProperty"
                )
                assert result == ""

    def test_stderr_message_format(self, shell_with_mocks, capsys):
        """Test that STDERR messages follow the specified format."""
        mock_element = MockSetup.create_mock_wall_entity()

        with patch(
            "ifcopenshell.util.selector.get_element_value",
            side_effect=Exception("Property not found"),
        ):
            result = shell_with_mocks.value_extractor.extract_element_value(
                mock_element, "BadProperty"
            )

            assert result == ""
            assert_error_output_contains(
                capsys, "Property 'BadProperty' not found on entity #1"
            )
