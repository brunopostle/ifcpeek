"""Essential unit tests for IfcPeek value extraction functionality."""

import pytest
from unittest.mock import Mock
import sys
from io import StringIO
from pathlib import Path
import tempfile
import os

# Import the shell class to test
from ifcpeek.shell import IfcPeek


class TestQueryParsing:
    """Test the query parsing functionality."""

    def test_parse_simple_query(self, monkeypatch):
        """Test parsing of simple query without semicolons."""
        shell = self._create_test_shell(monkeypatch)
        filter_query, value_queries, is_combined = shell._parse_combined_query(
            "IfcWall"
        )

        assert filter_query == "IfcWall"
        assert value_queries == []
        assert is_combined is False

    def test_parse_combined_query_single_value(self, monkeypatch):
        """Test parsing of combined query with single value extraction."""
        shell = self._create_test_shell(monkeypatch)
        filter_query, value_queries, is_combined = shell._parse_combined_query(
            "IfcWall ; Name"
        )

        assert filter_query == "IfcWall"
        assert value_queries == ["Name"]
        assert is_combined is True

    def test_parse_combined_query_multiple_values(self, monkeypatch):
        """Test parsing of combined query with multiple value extractions."""
        shell = self._create_test_shell(monkeypatch)
        filter_query, value_queries, is_combined = shell._parse_combined_query(
            "IfcWall ; Name ; type.Name ; material.Name"
        )

        assert filter_query == "IfcWall"
        assert value_queries == ["Name", "type.Name", "material.Name"]
        assert is_combined is True

    def test_parse_query_empty_filter(self, monkeypatch):
        """Test parsing with empty filter query (should raise ValueError)."""
        shell = self._create_test_shell(monkeypatch)
        with pytest.raises(ValueError, match="Filter query.*cannot be empty"):
            shell._parse_combined_query(" ; Name ; type.Name")

    def _create_test_shell(self, monkeypatch):
        """Helper to create a test shell with proper monkeypatching."""
        # Create a temporary real file to avoid file system issues
        with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as tmp:
            tmp.write(
                b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;"
            )
            tmp_path = tmp.name

        try:
            # Mock the components that need mocking
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_session = Mock()

            # Use monkeypatch to ensure proper cleanup
            monkeypatch.setattr("ifcopenshell.open", lambda x: mock_model)
            monkeypatch.setattr(
                "ifcpeek.shell.PromptSession", lambda **kwargs: mock_session
            )
            monkeypatch.setattr(
                "ifcpeek.shell.get_history_file_path", lambda: Path("/tmp/history")
            )

            # Create shell with real file
            shell = IfcPeek(tmp_path)
            shell.session = mock_session
            shell.model = mock_model

            return shell
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except:
                pass


class TestInputProcessing:
    """Test the input processing with routing logic."""

    def test_process_input_simple_query(self, monkeypatch):
        """Test processing simple query (backwards compatibility)."""
        shell = self._create_test_shell(monkeypatch)

        # Mock the execution method
        mock_execute = Mock()
        monkeypatch.setattr(shell, "_execute_query", mock_execute)

        result = shell._process_input("IfcWall")
        mock_execute.assert_called_once_with("IfcWall")
        assert result is True

    def test_process_input_combined_query(self, monkeypatch):
        """Test processing combined query."""
        shell = self._create_test_shell(monkeypatch)

        # Mock the execution method
        mock_execute_combined = Mock()
        monkeypatch.setattr(shell, "_execute_combined_query", mock_execute_combined)

        result = shell._process_input("IfcWall ; Name")
        mock_execute_combined.assert_called_once_with("IfcWall", ["Name"])
        assert result is True

    def test_process_input_routing_logic(self, monkeypatch):
        """Test that routing logic works correctly."""
        shell = self._create_test_shell(monkeypatch)

        # Mock both execution methods
        mock_simple = Mock()
        mock_combined = Mock()
        monkeypatch.setattr(shell, "_execute_query", mock_simple)
        monkeypatch.setattr(shell, "_execute_combined_query", mock_combined)

        # Simple query should route to _execute_query
        shell._process_input("IfcWall")
        mock_simple.assert_called_once_with("IfcWall")
        assert not mock_combined.called

        # Reset mocks
        mock_simple.reset_mock()
        mock_combined.reset_mock()

        # Combined query should route to _execute_combined_query
        shell._process_input("IfcWall ; Name")
        mock_combined.assert_called_once_with("IfcWall", ["Name"])
        assert not mock_simple.called

    def _create_test_shell(self, monkeypatch):
        """Helper to create a test shell with proper monkeypatching."""
        # Create a temporary real file to avoid file system issues
        with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as tmp:
            tmp.write(
                b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;"
            )
            tmp_path = tmp.name

        try:
            # Mock the components that need mocking
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_session = Mock()

            # Use monkeypatch to ensure proper cleanup
            monkeypatch.setattr("ifcopenshell.open", lambda x: mock_model)
            monkeypatch.setattr(
                "ifcpeek.shell.PromptSession", lambda **kwargs: mock_session
            )
            monkeypatch.setattr(
                "ifcpeek.shell.get_history_file_path", lambda: Path("/tmp/history")
            )

            # Create shell with real file
            shell = IfcPeek(tmp_path)
            shell.session = mock_session
            shell.model = mock_model

            return shell
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except:
                pass


class TestValueExtraction:
    """Test the value extraction functionality."""

    def test_extract_element_value_success(self, monkeypatch):
        """Test successful value extraction."""
        shell = self._create_test_shell(monkeypatch)
        mock_element = Mock()
        mock_element.id.return_value = 123

        # Mock the ifcopenshell function
        mock_get_value = Mock(return_value="TestWall")
        monkeypatch.setattr(
            "ifcopenshell.util.selector.get_element_value", mock_get_value
        )

        result = shell._extract_element_value(mock_element, "Name")

        assert result == "TestWall"
        mock_get_value.assert_called_once_with(mock_element, "Name")

    def test_extract_element_value_none(self, monkeypatch):
        """Test value extraction returning None."""
        shell = self._create_test_shell(monkeypatch)
        mock_element = Mock()
        mock_element.id.return_value = 123

        # Mock the ifcopenshell function
        mock_get_value = Mock(return_value=None)
        monkeypatch.setattr(
            "ifcopenshell.util.selector.get_element_value", mock_get_value
        )

        result = shell._extract_element_value(mock_element, "NonExistentProperty")

        assert result == ""

    def test_extract_element_value_list(self, monkeypatch):
        """Test value extraction returning a list."""
        shell = self._create_test_shell(monkeypatch)
        mock_element = Mock()
        mock_element.id.return_value = 123

        # Mock the ifcopenshell function
        mock_get_value = Mock(return_value=["item1", "item2", "item3"])
        monkeypatch.setattr(
            "ifcopenshell.util.selector.get_element_value", mock_get_value
        )

        result = shell._extract_element_value(mock_element, "SomeListProperty")

        assert result == "<List[3]>"

    def _create_test_shell(self, monkeypatch):
        """Helper to create a test shell with proper monkeypatching."""
        # Create a temporary real file to avoid file system issues
        with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as tmp:
            tmp.write(
                b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;"
            )
            tmp_path = tmp.name

        try:
            # Mock the components that need mocking
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_session = Mock()

            # Use monkeypatch to ensure proper cleanup
            monkeypatch.setattr("ifcopenshell.open", lambda x: mock_model)
            monkeypatch.setattr(
                "ifcpeek.shell.PromptSession", lambda **kwargs: mock_session
            )
            monkeypatch.setattr(
                "ifcpeek.shell.get_history_file_path", lambda: Path("/tmp/history")
            )

            # Create shell with real file
            shell = IfcPeek(tmp_path)
            shell.session = mock_session
            shell.model = mock_model

            return shell
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except:
                pass


class TestOutputFormatting:
    """Test the output formatting functionality."""

    def test_format_value_output_single(self, monkeypatch):
        """Test formatting single value (no tabs)."""
        shell = self._create_test_shell(monkeypatch)
        result = shell._format_value_output(["TestWall"])
        assert result == "TestWall"

    def test_format_value_output_multiple(self, monkeypatch):
        """Test formatting multiple values (tab-separated)."""
        shell = self._create_test_shell(monkeypatch)
        result = shell._format_value_output(["TestWall", "WallType01", "Concrete"])
        assert result == "TestWall\tWallType01\tConcrete"

    def test_format_value_output_with_tabs(self, monkeypatch):
        """Test formatting values containing tabs (should be replaced with spaces)."""
        shell = self._create_test_shell(monkeypatch)
        result = shell._format_value_output(["Test\tWall", "Type\t01"])
        assert result == "Test Wall\tType 01"

    def _create_test_shell(self, monkeypatch):
        """Helper to create a test shell with proper monkeypatching."""
        # Create a temporary real file to avoid file system issues
        with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as tmp:
            tmp.write(
                b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;"
            )
            tmp_path = tmp.name

        try:
            # Mock the components that need mocking
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_session = Mock()

            # Use monkeypatch to ensure proper cleanup
            monkeypatch.setattr("ifcopenshell.open", lambda x: mock_model)
            monkeypatch.setattr(
                "ifcpeek.shell.PromptSession", lambda **kwargs: mock_session
            )
            monkeypatch.setattr(
                "ifcpeek.shell.get_history_file_path", lambda: Path("/tmp/history")
            )

            # Create shell with real file
            shell = IfcPeek(tmp_path)
            shell.session = mock_session
            shell.model = mock_model

            return shell
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except:
                pass


class TestCombinedQueryExecution:
    """Test the combined query execution functionality."""

    def test_execute_combined_query_no_results(self, monkeypatch):
        """Test combined query execution with no filter results."""
        shell = self._create_test_shell(monkeypatch)

        # Mock filter_elements to return no results
        mock_filter = Mock(return_value=[])
        monkeypatch.setattr("ifcopenshell.util.selector.filter_elements", mock_filter)

        # Capture stdout
        original_stdout = sys.stdout
        captured_output = StringIO()
        monkeypatch.setattr(sys, "stdout", captured_output)

        try:
            shell._execute_combined_query("IfcWall", ["Name"])

            # Should produce no output when no elements found
            assert captured_output.getvalue() == ""
        finally:
            monkeypatch.setattr(sys, "stdout", original_stdout)

    def test_execute_combined_query_with_values(self, monkeypatch):
        """Test combined query execution with value queries."""
        shell = self._create_test_shell(monkeypatch)

        mock_element1 = Mock()
        mock_element1.id.return_value = 123
        mock_element2 = Mock()
        mock_element2.id.return_value = 124
        mock_elements = [mock_element1, mock_element2]

        # Mock filter_elements to return test elements
        mock_filter = Mock(return_value=mock_elements)
        monkeypatch.setattr("ifcopenshell.util.selector.filter_elements", mock_filter)

        # Mock the extract method to return test values
        def mock_extract_side_effect(element, query):
            if element.id() == 123:
                return "Wall1" if query == "Name" else "Type1"
            else:
                return "Wall2" if query == "Name" else "Type2"

        monkeypatch.setattr(shell, "_extract_element_value", mock_extract_side_effect)

        # Capture stdout
        original_stdout = sys.stdout
        captured_output = StringIO()
        monkeypatch.setattr(sys, "stdout", captured_output)

        try:
            shell._execute_combined_query("IfcWall", ["Name", "type.Name"])

            output = captured_output.getvalue().strip().split("\n")
            assert len(output) == 2
            assert output[0] == "Wall1\tType1"
            assert output[1] == "Wall2\tType2"
        finally:
            monkeypatch.setattr(sys, "stdout", original_stdout)

    def _create_test_shell(self, monkeypatch):
        """Helper to create a test shell with proper monkeypatching."""
        # Create a temporary real file to avoid file system issues
        with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as tmp:
            tmp.write(
                b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;"
            )
            tmp_path = tmp.name

        try:
            # Mock the components that need mocking
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_session = Mock()

            # Use monkeypatch to ensure proper cleanup
            monkeypatch.setattr("ifcopenshell.open", lambda x: mock_model)
            monkeypatch.setattr(
                "ifcpeek.shell.PromptSession", lambda **kwargs: mock_session
            )
            monkeypatch.setattr(
                "ifcpeek.shell.get_history_file_path", lambda: Path("/tmp/history")
            )

            # Create shell with real file
            shell = IfcPeek(tmp_path)
            shell.session = mock_session
            shell.model = mock_model

            return shell
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except:
                pass


class TestBackwardsCompatibility:
    """Test that existing functionality still works unchanged."""

    def test_simple_queries_unchanged(self, monkeypatch):
        """Test that simple queries work exactly as before."""
        shell = self._create_test_shell(monkeypatch)
        test_queries = [
            "IfcWall",
            "IfcWall, material=concrete",
            "IfcElement, Name=Door-01",
        ]

        for query in test_queries:
            # Mock the execution method for each query
            mock_execute = Mock()
            monkeypatch.setattr(shell, "_execute_query", mock_execute)

            result = shell._process_input(query)

            # Should route to simple query execution
            mock_execute.assert_called_once_with(query)
            assert result is True

    def test_builtin_commands_unchanged(self, monkeypatch):
        """Test that built-in commands work exactly as before."""
        shell = self._create_test_shell(monkeypatch)
        commands = ["/help", "/exit", "/quit"]

        for command in commands:
            # Mock the command method
            command_method = shell.BUILTIN_COMMANDS[command]
            mock_command = Mock(return_value=True)
            monkeypatch.setattr(shell, command_method, mock_command)

            result = shell._process_input(command)
            mock_command.assert_called_once()
            assert result is True

    def _create_test_shell(self, monkeypatch):
        """Helper to create a test shell with proper monkeypatching."""
        # Create a temporary real file to avoid file system issues
        with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as tmp:
            tmp.write(
                b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;"
            )
            tmp_path = tmp.name

        try:
            # Mock the components that need mocking
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_session = Mock()

            # Use monkeypatch to ensure proper cleanup
            monkeypatch.setattr("ifcopenshell.open", lambda x: mock_model)
            monkeypatch.setattr(
                "ifcpeek.shell.PromptSession", lambda **kwargs: mock_session
            )
            monkeypatch.setattr(
                "ifcpeek.shell.get_history_file_path", lambda: Path("/tmp/history")
            )

            # Create shell with real file
            shell = IfcPeek(tmp_path)
            shell.session = mock_session
            shell.model = mock_model

            return shell
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except:
                pass


class TestIntegrationScenarios:
    """Test complete integration scenarios."""

    def test_complete_workflow_multiple_values(self, monkeypatch):
        """Test complete workflow with multiple value extractions."""
        shell = self._create_test_shell(monkeypatch)

        # Setup mock elements
        mock_wall = Mock()
        mock_wall.id.return_value = 123
        mock_elements = [mock_wall]

        # Mock filter_elements
        mock_filter = Mock(return_value=mock_elements)
        monkeypatch.setattr("ifcopenshell.util.selector.filter_elements", mock_filter)

        # Mock get_element_value
        def mock_get_value_side_effect(element, query):
            value_map = {
                "Name": "TestWall",
                "type.Name": "WallType01",
                "material.Name": "Concrete",
            }
            return value_map.get(query, "")

        mock_get_value = Mock(side_effect=mock_get_value_side_effect)
        monkeypatch.setattr(
            "ifcopenshell.util.selector.get_element_value", mock_get_value
        )

        # Capture stdout
        original_stdout = sys.stdout
        captured_output = StringIO()
        monkeypatch.setattr(sys, "stdout", captured_output)

        try:
            # Execute the complete workflow
            result = shell._process_input("IfcWall ; Name ; type.Name ; material.Name")

            # Verify execution
            assert result is True
            output = captured_output.getvalue().strip()
            assert output == "TestWall\tWallType01\tConcrete"
        finally:
            monkeypatch.setattr(sys, "stdout", original_stdout)

    def _create_test_shell(self, monkeypatch):
        """Helper to create a test shell with proper monkeypatching."""
        # Create a temporary real file to avoid file system issues
        with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as tmp:
            tmp.write(
                b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;"
            )
            tmp_path = tmp.name

        try:
            # Mock the components that need mocking
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_session = Mock()

            # Use monkeypatch to ensure proper cleanup
            monkeypatch.setattr("ifcopenshell.open", lambda x: mock_model)
            monkeypatch.setattr(
                "ifcpeek.shell.PromptSession", lambda **kwargs: mock_session
            )
            monkeypatch.setattr(
                "ifcpeek.shell.get_history_file_path", lambda: Path("/tmp/history")
            )

            # Create shell with real file
            shell = IfcPeek(tmp_path)
            shell.session = mock_session
            shell.model = mock_model

            return shell
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except:
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
