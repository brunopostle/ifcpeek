"""
Comprehensive unit tests for value extraction functionality.
This file tests both individual methods and integration scenarios.
"""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path
import tempfile
import os

from ifcpeek.shell import IfcPeek


class TestExtractElementValue:
    """Test the _extract_element_value method."""

    def test_extract_simple_string_value(self, shell_fixture):
        """Test extracting simple string value."""
        shell = shell_fixture
        mock_element = Mock()
        mock_element.id.return_value = 123

        with patch(
            "ifcopenshell.util.selector.get_element_value", return_value="TestWall"
        ):
            result = shell._extract_element_value(mock_element, "Name")
            assert result == "TestWall"

    def test_extract_numeric_value(self, shell_fixture):
        """Test extracting numeric value."""
        shell = shell_fixture
        mock_element = Mock()
        mock_element.id.return_value = 123

        with patch("ifcopenshell.util.selector.get_element_value", return_value=2.5):
            result = shell._extract_element_value(mock_element, "Height")
            assert result == "2.5"

    def test_extract_boolean_value(self, shell_fixture):
        """Test extracting boolean value."""
        shell = shell_fixture
        mock_element = Mock()
        mock_element.id.return_value = 123

        with patch("ifcopenshell.util.selector.get_element_value", return_value=True):
            result = shell._extract_element_value(mock_element, "IsExternal")
            assert result == "True"

    def test_extract_none_value(self, shell_fixture):
        """Test extracting None value returns empty string."""
        shell = shell_fixture
        mock_element = Mock()
        mock_element.id.return_value = 123

        with patch("ifcopenshell.util.selector.get_element_value", return_value=None):
            result = shell._extract_element_value(mock_element, "NonExistentProperty")
            assert result == ""

    def test_extract_list_value(self, shell_fixture):
        """Test extracting list value returns placeholder."""
        shell = shell_fixture
        mock_element = Mock()
        mock_element.id.return_value = 123

        test_list = ["item1", "item2", "item3"]
        with patch(
            "ifcopenshell.util.selector.get_element_value", return_value=test_list
        ):
            result = shell._extract_element_value(mock_element, "ListProperty")
            assert result == "<List[3]>"

    def test_extract_tuple_value(self, shell_fixture):
        """Test extracting tuple value returns placeholder."""
        shell = shell_fixture
        mock_element = Mock()
        mock_element.id.return_value = 123

        test_tuple = ("x", "y", "z")
        with patch(
            "ifcopenshell.util.selector.get_element_value", return_value=test_tuple
        ):
            result = shell._extract_element_value(mock_element, "TupleProperty")
            assert result == "<List[3]>"

    def test_extract_complex_object_short(self, shell_fixture):
        """Test extracting complex object with short string representation."""
        shell = shell_fixture
        mock_element = Mock()
        mock_element.id.return_value = 123

        class MockObject:
            def __str__(self):
                return "ShortObject"

        test_object = MockObject()
        with patch(
            "ifcopenshell.util.selector.get_element_value", return_value=test_object
        ):
            result = shell._extract_element_value(mock_element, "ObjectProperty")
            assert result == "ShortObject"

    def test_extract_complex_object_long(self, shell_fixture):
        """Test extracting complex object with long string representation."""
        shell = shell_fixture
        mock_element = Mock()
        mock_element.id.return_value = 123

        class MockLongObject:
            def __str__(self):
                return "A" * 150  # Long string > 100 chars

        test_object = MockLongObject()
        with patch(
            "ifcopenshell.util.selector.get_element_value", return_value=test_object
        ):
            result = shell._extract_element_value(mock_element, "LongObjectProperty")
            assert result == "<Object[MockLongObject]>"

    def test_extract_exception_handling(self, shell_fixture, capsys):
        """Test exception handling returns empty string and logs to STDERR."""
        shell = shell_fixture
        mock_element = Mock()
        mock_element.id.return_value = 123

        with patch(
            "ifcopenshell.util.selector.get_element_value",
            side_effect=Exception("Property not found"),
        ):
            result = shell._extract_element_value(mock_element, "BadProperty")

            assert result == ""

            captured = capsys.readouterr()
            assert "Property 'BadProperty' not found on entity #123" in captured.err

    @pytest.fixture
    def shell_fixture(self):
        """Create a shell fixture for testing."""
        return self._create_test_shell()

    def _create_test_shell(self):
        """Helper to create a test shell."""
        with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as tmp:
            tmp.write(
                b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;"
            )
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


class TestDataTypeHandling:
    """Test handling of various IFC data types."""

    def test_handle_string_data_types(self, shell_fixture):
        """Test handling of string data types."""
        shell = shell_fixture
        mock_element = Mock()
        mock_element.id.return_value = 123

        test_cases = [
            ("Simple String", "Simple String"),
            ("String with spaces", "String with spaces"),
            ("String with 'quotes'", "String with 'quotes'"),
            ('String with "double quotes"', 'String with "double quotes"'),
            ("", ""),  # Empty string
        ]

        for input_value, expected_output in test_cases:
            with patch(
                "ifcopenshell.util.selector.get_element_value", return_value=input_value
            ):
                result = shell._extract_element_value(mock_element, "StringProperty")
                assert result == expected_output

    def test_handle_numeric_data_types(self, shell_fixture):
        """Test handling of numeric data types."""
        shell = shell_fixture
        mock_element = Mock()
        mock_element.id.return_value = 123

        test_cases = [
            (42, "42"),
            (3.14159, "3.14159"),
            (0, "0"),
            (-1, "-1"),
            (0.0, "0.0"),
            (1e6, "1000000.0"),
        ]

        for input_value, expected_output in test_cases:
            with patch(
                "ifcopenshell.util.selector.get_element_value", return_value=input_value
            ):
                result = shell._extract_element_value(mock_element, "NumericProperty")
                assert result == expected_output

    def test_handle_boolean_data_types(self, shell_fixture):
        """Test handling of boolean data types."""
        shell = shell_fixture
        mock_element = Mock()
        mock_element.id.return_value = 123

        test_cases = [
            (True, "True"),
            (False, "False"),
        ]

        for input_value, expected_output in test_cases:
            with patch(
                "ifcopenshell.util.selector.get_element_value", return_value=input_value
            ):
                result = shell._extract_element_value(mock_element, "BooleanProperty")
                assert result == expected_output

    def test_handle_list_data_types(self, shell_fixture):
        """Test handling of list and tuple data types."""
        shell = shell_fixture
        mock_element = Mock()
        mock_element.id.return_value = 123

        test_cases = [
            ([], "<List[0]>"),
            ([1, 2, 3], "<List[3]>"),
            (["a", "b", "c", "d", "e"], "<List[5]>"),
            ((1, 2), "<List[2]>"),
            (tuple(), "<List[0]>"),
        ]

        for input_value, expected_output in test_cases:
            with patch(
                "ifcopenshell.util.selector.get_element_value", return_value=input_value
            ):
                result = shell._extract_element_value(mock_element, "ListProperty")
                assert result == expected_output

    @pytest.fixture
    def shell_fixture(self):
        """Create a shell fixture for testing."""
        return self._create_test_shell()

    def _create_test_shell(self):
        """Helper to create a test shell."""
        with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as tmp:
            tmp.write(
                b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;"
            )
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


class TestErrorReporting:
    """Test error reporting functionality."""

    def test_stderr_message_format(self, shell_fixture, capsys):
        """Test that STDERR messages follow the specified format."""
        shell = shell_fixture
        mock_element = Mock()
        mock_element.id.return_value = 123

        with patch(
            "ifcopenshell.util.selector.get_element_value",
            side_effect=Exception("Property not found"),
        ):
            result = shell._extract_element_value(mock_element, "BadProperty")

            assert result == ""

            captured = capsys.readouterr()
            # Check exact format: "Property 'query' not found on entity #id"
            assert "Property 'BadProperty' not found on entity #123" in captured.err

    def test_no_shell_crash_on_errors(self, shell_fixture):
        """Test that the shell never crashes due to value extraction errors."""
        shell = shell_fixture

        mock_element = Mock()
        mock_element.id.return_value = 123

        # Test various types of exceptions
        exception_types = [
            Exception("Generic error"),
            ValueError("Value error"),
            AttributeError("Attribute error"),
            KeyError("Key error"),
            RuntimeError("Runtime error"),
        ]

        for exception in exception_types:
            with patch(
                "ifcopenshell.util.selector.get_element_value", side_effect=exception
            ):
                # Should not raise any exceptions
                result = shell._extract_element_value(mock_element, "BadProperty")
                assert result == ""

    def test_continuing_after_partial_failures(self, shell_fixture):
        """Test that processing continues even when some extractions fail."""
        shell = shell_fixture

        mock_element = Mock()
        mock_element.id.return_value = 123
        elements = [mock_element]
        value_queries = ["GoodProperty1", "BadProperty", "GoodProperty2"]

        def mock_extract_side_effect(element, query):
            if "Good" in query:
                return f"Value for {query}"
            else:
                raise Exception("Property not found")

        with patch(
            "ifcopenshell.util.selector.get_element_value",
            side_effect=mock_extract_side_effect,
        ):
            results = shell._process_value_queries(elements, value_queries)

            # Should have results for all queries, with empty strings for failed ones
            assert len(results) == 1
            assert len(results[0]) == 3
            assert results[0][0] == "Value for GoodProperty1"
            assert results[0][1] == ""  # Failed extraction
            assert results[0][2] == "Value for GoodProperty2"

    @pytest.fixture
    def shell_fixture(self):
        """Create a shell fixture for testing."""
        return self._create_test_shell()

    def _create_test_shell(self):
        """Helper to create a test shell."""
        with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as tmp:
            tmp.write(
                b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;"
            )
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


class TestPerformanceAndEdgeCases:
    """Test performance and edge case scenarios."""

    def test_large_element_list_processing(self, shell_fixture):
        """Test processing large lists of elements."""
        shell = shell_fixture

        # Create 100 mock elements
        elements = []
        for i in range(100):
            mock_element = Mock()
            mock_element.id.return_value = i
            elements.append(mock_element)

        value_queries = ["Name", "type.Name"]

        def mock_extract_side_effect(element, query):
            element_id = element.id()
            if query == "Name":
                return f"Element{element_id}"
            else:
                return f"Type{element_id}"

        with patch(
            "ifcopenshell.util.selector.get_element_value",
            side_effect=mock_extract_side_effect,
        ):
            results = shell._process_value_queries(elements, value_queries)

            assert len(results) == 100
            for i, result in enumerate(results):
                assert result == [f"Element{i}", f"Type{i}"]

    def test_many_value_queries(self, shell_fixture):
        """Test processing many value queries."""
        shell = shell_fixture

        mock_element = Mock()
        mock_element.id.return_value = 123
        elements = [mock_element]

        # Create 50 value queries
        value_queries = [f"Property{i}" for i in range(50)]

        def mock_extract_side_effect(element, query):
            return f"Value for {query}"

        with patch(
            "ifcopenshell.util.selector.get_element_value",
            side_effect=mock_extract_side_effect,
        ):
            results = shell._process_value_queries(elements, value_queries)

            assert len(results) == 1
            assert len(results[0]) == 50
            for i, value in enumerate(results[0]):
                assert value == f"Value for Property{i}"

    def test_empty_input_combinations(self, shell_fixture):
        """Test various empty input combinations."""
        shell = shell_fixture

        test_cases = [
            ([], []),  # Empty elements and queries
            ([], ["Name"]),  # Empty elements, non-empty queries
            ([Mock()], []),  # Non-empty elements, empty queries
        ]

        for elements, value_queries in test_cases:
            results = shell._process_value_queries(elements, value_queries)

            if not elements:
                assert results == []
            else:
                assert len(results) == len(elements)
                for result in results:
                    assert len(result) == len(value_queries)

    def test_unicode_property_names(self, shell_fixture):
        """Test handling of Unicode property names."""
        shell = shell_fixture

        mock_element = Mock()
        mock_element.id.return_value = 123

        unicode_properties = [
            "属性名称",  # Chinese
            "свойство",  # Russian
            "プロパティ",  # Japanese
            "خاصية",  # Arabic
        ]

        for prop_name in unicode_properties:
            with patch(
                "ifcopenshell.util.selector.get_element_value",
                return_value="Unicode value",
            ):
                result = shell._extract_element_value(mock_element, prop_name)
                assert result == "Unicode value"

    @pytest.fixture
    def shell_fixture(self):
        """Create a shell fixture for testing."""
        return self._create_test_shell()

    def _create_test_shell(self):
        """Helper to create a test shell."""
        with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as tmp:
            tmp.write(
                b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;"
            )
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


class TestRealWorldScenarios:
    """Test realistic usage scenarios with IFC properties."""

    def test_common_ifc_properties(self, shell_fixture):
        """Test extraction of common IFC properties."""
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
            ("building.Name", "Main Building"),
            ("Qto_WallBaseQuantities.Length", "5.0"),
            ("Qto_WallBaseQuantities.Width", "0.2"),
            ("Qto_WallBaseQuantities.Height", "3.0"),
        ]

        for property_name, expected_value in common_properties:
            with patch(
                "ifcopenshell.util.selector.get_element_value",
                return_value=expected_value,
            ):
                result = shell._extract_element_value(mock_element, property_name)
                assert result == expected_value

    def test_property_set_patterns(self, shell_fixture):
        """Test extraction of property set patterns."""
        shell = shell_fixture
        mock_element = Mock()
        mock_element.id.return_value = 123

        # Test regex property set patterns
        regex_properties = [
            ("/Pset_.*Common/.Status", "Existing"),
            ("/Pset_.*Common/.IsExternal", "False"),
            ("/Qto_.*Quantities/.NetVolume", "15.5"),
        ]

        for property_name, expected_value in regex_properties:
            with patch(
                "ifcopenshell.util.selector.get_element_value",
                return_value=expected_value,
            ):
                result = shell._extract_element_value(mock_element, property_name)
                assert result == expected_value

    def test_hierarchical_properties(self, shell_fixture):
        """Test extraction of hierarchical properties."""
        shell = shell_fixture
        mock_element = Mock()
        mock_element.id.return_value = 123

        # Test hierarchical navigation
        hierarchical_properties = [
            ("container.Name", "Space-01"),
            ("space.Name", "Office 101"),
            ("storey.Name", "Ground Floor"),
            ("building.Name", "Building A"),
            ("site.Name", "Main Site"),
            ("parent.Name", "Parent Element"),
        ]

        for property_name, expected_value in hierarchical_properties:
            with patch(
                "ifcopenshell.util.selector.get_element_value",
                return_value=expected_value,
            ):
                result = shell._extract_element_value(mock_element, property_name)
                assert result == expected_value

    def test_coordinate_properties(self, shell_fixture):
        """Test extraction of coordinate and geometry properties."""
        shell = shell_fixture
        mock_element = Mock()
        mock_element.id.return_value = 123

        # Test coordinate properties
        coordinate_properties = [
            ("x", "10.5"),
            ("y", "20.0"),
            ("z", "3.0"),
            ("easting", "501234.56"),
            ("northing", "4567890.12"),
            ("elevation", "125.75"),
        ]

        for property_name, expected_value in coordinate_properties:
            with patch(
                "ifcopenshell.util.selector.get_element_value",
                return_value=float(expected_value),
            ):
                result = shell._extract_element_value(mock_element, property_name)
                assert result == expected_value

    @pytest.fixture
    def shell_fixture(self):
        """Create a shell fixture for testing."""
        return self._create_test_shell()

    def _create_test_shell(self):
        """Helper to create a test shell."""
        with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as tmp:
            tmp.write(
                b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;"
            )
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


class TestEndToEndIntegration:
    """Test complete end-to-end integration scenarios."""

    def test_complete_workflow_single_value(self, shell_fixture, capsys):
        """Test complete workflow from input to output with single value."""
        shell = shell_fixture

        mock_element = Mock()
        mock_element.id.return_value = 123

        # Mock the complete chain
        with patch(
            "ifcopenshell.util.selector.filter_elements", return_value=[mock_element]
        ):
            with patch(
                "ifcopenshell.util.selector.get_element_value", return_value="TestWall"
            ):
                # Test the complete _process_input workflow
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

    def test_complete_workflow_with_errors(self, shell_fixture, capsys):
        """Test complete workflow with some property extraction errors."""
        shell = shell_fixture

        mock_element = Mock()
        mock_element.id.return_value = 123

        def mock_get_value_with_errors(element, query):
            if query == "Name":
                return "TestWall"
            elif query == "BadProperty":
                raise Exception("Property not found")
            else:
                return "TypeName"

        with patch(
            "ifcopenshell.util.selector.filter_elements", return_value=[mock_element]
        ):
            with patch(
                "ifcopenshell.util.selector.get_element_value",
                side_effect=mock_get_value_with_errors,
            ):
                result = shell._process_input(
                    "IfcWall ; Name ; BadProperty ; type.Name"
                )

                assert result is True
                captured = capsys.readouterr()

                # Should have output with empty string for failed property
                assert captured.out.strip() == "TestWall\t\tTypeName"

                # Should have error message in STDERR
                assert "Property 'BadProperty' not found on entity #123" in captured.err

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

    def test_backwards_compatibility_commands(self, shell_fixture, capsys):
        """Test that built-in commands still work unchanged."""
        shell = shell_fixture

        # Test help command
        result = shell._process_input("/help")
        assert result is True

        captured = capsys.readouterr()
        assert "IfcPeek - Interactive IFC Model Query Tool" in captured.err

        # Test exit command
        result = shell._process_input("/exit")
        assert result is False

    @pytest.fixture
    def shell_fixture(self):
        """Create a shell fixture for testing."""
        return self._create_test_shell()

    def _create_test_shell(self):
        """Helper to create a test shell."""
        with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as tmp:
            tmp.write(
                b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;"
            )
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


class TestMockingAndFixtures:
    """Test that our mocking and fixtures work correctly."""

    def test_shell_fixture_creation(self, shell_fixture):
        """Test that shell fixture is created correctly."""
        shell = shell_fixture

        assert shell is not None
        assert hasattr(shell, "model")
        assert hasattr(shell, "_extract_element_value")
        assert hasattr(shell, "_process_value_queries")
        assert hasattr(shell, "_execute_combined_query")
        assert hasattr(shell, "_process_input")

    def test_ifcopenshell_mocking(self, shell_fixture):
        """Test that IfcOpenShell mocking works correctly."""
        shell = shell_fixture
        mock_element = Mock()
        mock_element.id.return_value = 999

        # Test that we can mock get_element_value
        with patch(
            "ifcopenshell.util.selector.get_element_value", return_value="MockedValue"
        ):
            result = shell._extract_element_value(mock_element, "TestProperty")
            assert result == "MockedValue"

    def test_filter_elements_mocking(self, shell_fixture):
        """Test that filter_elements mocking works correctly."""
        shell = shell_fixture

        mock_element = Mock()
        mock_element.id.return_value = 999

        with patch(
            "ifcopenshell.util.selector.filter_elements", return_value=[mock_element]
        ):
            with patch.object(
                shell, "_process_value_queries", return_value=[["TestValue"]]
            ):
                shell._execute_combined_query("IfcWall", ["Name"])
                # Should not raise any exceptions

    @pytest.fixture
    def shell_fixture(self):
        """Create a shell fixture for testing."""
        return self._create_test_shell()

    def _create_test_shell(self):
        """Helper to create a test shell."""
        with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as tmp:
            tmp.write(
                b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;"
            )
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


# Run tests if executed directly
if __name__ == "__main__":
    # Print test information
    print("Value Extraction Engine - Comprehensive Test Suite")
    print("=" * 60)
    print("Testing Phase 2 implementation:")
    print("  • _extract_element_value() method")
    print("  • _process_value_queries() method")
    print("  • Enhanced _execute_combined_query() integration")
    print("  • Error handling and data type support")
    print("  • End-to-end integration scenarios")
    print("=" * 60)

    # Run the tests with verbose output
    pytest.main([__file__, "-v", "--tb=short"])


class TestProcessValueQueries:
    """Test the _process_value_queries method."""

    def test_process_single_element_single_query(self, shell_fixture):
        """Test processing single element with single value query."""
        shell = shell_fixture

        mock_element = Mock()
        mock_element.id.return_value = 123
        elements = [mock_element]
        value_queries = ["Name"]

        with patch.object(shell, "_extract_element_value", return_value="TestWall"):
            results = shell._process_value_queries(elements, value_queries)

            assert len(results) == 1
            assert len(results[0]) == 1
            assert results[0][0] == "TestWall"

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
            shell, "_extract_element_value", side_effect=mock_extract_side_effect
        ):
            results = shell._process_value_queries(elements, value_queries)

            assert len(results) == 1
            assert len(results[0]) == 3
            assert results[0] == ["TestWall", "WallType01", "Concrete"]

    def test_process_multiple_elements_multiple_queries(self, shell_fixture):
        """Test processing multiple elements with multiple value queries."""
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
            shell, "_extract_element_value", side_effect=mock_extract_side_effect
        ):
            results = shell._process_value_queries(elements, value_queries)

            assert len(results) == 2
            assert results[0] == ["Wall1", "Type1"]
            assert results[1] == ["Wall2", "Type2"]

    def test_process_empty_elements(self, shell_fixture):
        """Test processing empty elements list."""
        shell = shell_fixture

        results = shell._process_value_queries([], ["Name"])
        assert results == []

    def test_process_empty_queries(self, shell_fixture):
        """Test processing with empty value queries."""
        shell = shell_fixture

        mock_element = Mock()
        mock_element.id.return_value = 123

        results = shell._process_value_queries([mock_element], [])
        assert len(results) == 1
        assert results[0] == []

    def test_process_with_extraction_errors(self, shell_fixture, capsys):
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
                return ""  # _extract_element_value handles errors internally

        with patch.object(
            shell, "_extract_element_value", side_effect=mock_extract_side_effect
        ):
            results = shell._process_value_queries(elements, value_queries)

            assert len(results) == 1
            assert results[0] == ["GoodValue", ""]

    def test_process_with_unexpected_error(self, shell_fixture, capsys):
        """Test handling of unexpected errors during processing."""
        shell = shell_fixture

        mock_element = Mock()
        mock_element.id.return_value = 123
        elements = [mock_element]
        value_queries = ["Name"]

        with patch.object(
            shell,
            "_extract_element_value",
            side_effect=RuntimeError("Unexpected error"),
        ):
            results = shell._process_value_queries(elements, value_queries)

            # Should handle error gracefully and continue
            assert len(results) == 1
            assert results[0] == [""]  # Empty string for failed extraction

            captured = capsys.readouterr()
            assert (
                "Unexpected error extracting 'Name' from element #123" in captured.err
            )

    @pytest.fixture
    def shell_fixture(self):
        """Create a shell fixture for testing."""
        return self._create_test_shell()

    def _create_test_shell(self):
        """Helper to create a test shell."""
        with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as tmp:
            tmp.write(
                b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;"
            )
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


class TestExecuteCombinedQueryIntegration:
    """Test integration of _process_value_queries with _execute_combined_query."""

    def test_combined_query_uses_batch_processing(self, shell_fixture, capsys):
        """Test that combined query uses the new batch processing method."""
        shell = shell_fixture

        mock_element1 = Mock()
        mock_element1.id.return_value = 123
        mock_element2 = Mock()
        mock_element2.id.return_value = 124
        mock_elements = [mock_element1, mock_element2]

        # Mock filter_elements to return test elements
        with patch(
            "ifcopenshell.util.selector.filter_elements", return_value=mock_elements
        ):
            # Mock _process_value_queries to return test data
            with patch.object(
                shell,
                "_process_value_queries",
                return_value=[["Wall1", "Type1"], ["Wall2", "Type2"]],
            ):

                shell._execute_combined_query("IfcWall", ["Name", "type.Name"])

                captured = capsys.readouterr()
                output_lines = captured.out.strip().split("\n")

                assert len(output_lines) == 2
                assert output_lines[0] == "Wall1\tType1"
                assert output_lines[1] == "Wall2\tType2"

    def test_combined_query_no_elements(self, shell_fixture, capsys):
        """Test combined query with no filter results."""
        shell = shell_fixture

        with patch("ifcopenshell.util.selector.filter_elements", return_value=[]):
            shell._execute_combined_query("IfcNonExistent", ["Name"])

            captured = capsys.readouterr()
            assert captured.out == ""  # No output for no results

    def test_combined_query_no_value_queries(self, shell_fixture, capsys):
        """Test combined query with no value queries falls back to entity output."""
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
                shell._execute_combined_query("IfcWall", [])

                captured = capsys.readouterr()
                assert "#123=IFCWALL" in captured.out

    def test_combined_query_filter_error(self, shell_fixture, capsys):
        """Test combined query handles filter errors gracefully."""
        shell = shell_fixture

        with patch(
            "ifcopenshell.util.selector.filter_elements",
            side_effect=Exception("Invalid filter"),
        ):
            shell._execute_combined_query("BadFilter[", ["Name"])

            captured = capsys.readouterr()
            # Check for the actual error format used in _execute_combined_query
            assert "IFC QUERY EXECUTION ERROR" in captured.err
            assert "Filter query: BadFilter[" in captured.err
            assert "Exception: Exception: Invalid filter" in captured.err
            assert "Query execution failed - shell will continue." in captured.err
            assert captured.out == ""  # No output on filter error

    def test_combined_query_value_processing_error(self, shell_fixture, capsys):
        """Test combined query handles value processing errors gracefully."""
        shell = shell_fixture

        mock_element = Mock()
        mock_element.id.return_value = 123

        with patch(
            "ifcopenshell.util.selector.filter_elements", return_value=[mock_element]
        ):
            with patch.object(
                shell,
                "_process_value_queries",
                side_effect=Exception("Processing failed"),
            ):
                shell._execute_combined_query("IfcWall", ["Name"])

                captured = capsys.readouterr()
                assert (
                    "Failed to process value queries: Processing failed" in captured.err
                )

    @pytest.fixture
    def shell_fixture(self):
        """Create a shell fixture for testing."""
        return self._create_test_shell()

    def _create_test_shell(self):
        """Helper to create a test shell."""
        with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as tmp:
            tmp.write(
                b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;"
            )
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
            pass
