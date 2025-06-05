"""Simplified shell tests using centralized test utilities."""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch

# Ensure paths are set up correctly
src_path = Path(__file__).parent.parent / "src"
tests_path = Path(__file__).parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
if str(tests_path) not in sys.path:
    sys.path.insert(0, str(tests_path))

from ifcpeek.shell import IfcPeek
from ifcpeek.exceptions import FileNotFoundError, InvalidIfcFileError
from test_utils import (
    ShellTestBase,
    QueryTestMixin,
    MockIfcEnvironment,
    MockSetup,
    assert_query_output_contains,
    assert_error_output_contains,
)


class TestIfcPeekInitialization(ShellTestBase):
    """Test IfcPeek class initialization with simplified setup."""

    def test_init_loads_ifc_model_successfully(self, shell_with_mocks):
        """Test IfcPeek initialization loads IFC model successfully."""
        assert shell_with_mocks.model is not None
        assert hasattr(shell_with_mocks, "session")

    def test_init_handles_ifcopenshell_errors(self, mock_ifc_file):
        """Test IfcPeek initialization handles IfcOpenShell loading errors."""
        with patch(
            "ifcpeek.shell.ifcopenshell.open",
            side_effect=RuntimeError("Invalid IFC format"),
        ):
            with pytest.raises(InvalidIfcFileError) as exc_info:
                IfcPeek(str(mock_ifc_file))
            assert "Failed to load IFC file" in str(exc_info.value)

    def test_init_with_nonexistent_file(self, nonexistent_file):
        """Test IfcPeek initialization with non-existent file."""
        with pytest.raises(FileNotFoundError) as exc_info:
            IfcPeek(str(nonexistent_file))
        assert "not found" in str(exc_info.value)

    def test_init_with_invalid_file_extension(self, invalid_file):
        """Test IfcPeek initialization with invalid file extension."""
        with pytest.raises(InvalidIfcFileError) as exc_info:
            IfcPeek(str(invalid_file))
        assert "does not appear to be an IFC file" in str(exc_info.value)


class TestQueryExecution(ShellTestBase, QueryTestMixin):
    """Test IFC query execution with simplified setup."""

    def test_process_input_executes_queries(
        self, shell_with_mocks, mock_wall, mock_selector, capsys
    ):
        """Test that _process_input executes IFC queries."""
        self.setup_successful_query_mock(mock_selector, [mock_wall])

        result = shell_with_mocks._process_input("IfcWall")

        assert result is True
        assert_query_output_contains(capsys, "#1=IFCWALL('wall-guid-001'")
        mock_selector.assert_called_once_with(shell_with_mocks.model, "IfcWall")

    def test_process_input_handles_invalid_queries(
        self, shell_with_mocks, mock_selector, capsys
    ):
        """Test that _process_input handles invalid IFC queries with error messages."""
        self.setup_failing_query_mock(
            mock_selector, Exception("Invalid selector syntax")
        )

        result = shell_with_mocks._process_input("invalid query")

        assert result is True
        assert_error_output_contains(capsys, "IFC QUERY EXECUTION ERROR")

    def test_process_input_handles_empty_input(self, shell_with_mocks, mock_selector):
        """Test that _process_input handles empty input correctly."""
        result = shell_with_mocks._process_input("")

        assert result is True
        mock_selector.assert_not_called()

    def test_successful_query_with_multiple_entities(
        self, shell_with_mocks, mock_wall, mock_door, mock_selector, capsys
    ):
        """Test successful query with multiple entities."""
        self.setup_successful_query_mock(mock_selector, [mock_wall, mock_door])

        shell_with_mocks._execute_query("IfcElement")

        captured = capsys.readouterr()
        assert "#1=IFCWALL('wall-guid-001'" in captured.out
        assert "#2=IFCDOOR('door-guid-001'" in captured.out


class TestBuiltinCommands(ShellTestBase):
    """Test built-in command functionality with simplified setup."""

    def test_help_command(self, shell_with_mocks, capsys):
        """Test that /help command displays help text."""
        result = shell_with_mocks._process_input("/help")

        assert result is True
        assert_error_output_contains(
            capsys, "IfcPeek - Interactive IFC Model Query Tool"
        )

    def test_exit_commands(self, shell_with_mocks):
        """Test that /exit and /quit commands return False."""
        assert shell_with_mocks._process_input("/exit") is False
        assert shell_with_mocks._process_input("/quit") is False

    def test_commands_have_priority_over_queries(self, shell_with_mocks, mock_selector):
        """Test that commands take priority over query parsing."""
        # Even if selector is configured, commands should not trigger it
        result = shell_with_mocks._process_input("/help")

        assert result is True
        mock_selector.assert_not_called()


class TestShellRunMethod(ShellTestBase):
    """Test the shell run method with simplified setup."""

    def test_run_handles_eof_gracefully(self, shell_with_mocks, capsys):
        """Test run method handles EOFError (Ctrl-D) gracefully."""
        with patch.object(shell_with_mocks, "session") as mock_session:
            mock_session.prompt.side_effect = EOFError
            shell_with_mocks.run()

        assert_error_output_contains(capsys, "Goodbye!")

    def test_run_handles_keyboard_interrupt(self, shell_with_mocks, capsys):
        """Test run method handles KeyboardInterrupt (Ctrl-C) gracefully."""
        with patch.object(shell_with_mocks, "session") as mock_session:
            mock_session.prompt.side_effect = [KeyboardInterrupt, EOFError]
            shell_with_mocks.run()

        captured = capsys.readouterr()
        assert "(Use Ctrl-D to exit)" in captured.err
        assert "Goodbye!" in captured.err


class TestErrorRecovery(ShellTestBase, QueryTestMixin):
    """Test error recovery scenarios with simplified setup."""

    def test_shell_continues_after_query_errors(
        self, shell_with_mocks, mock_wall, mock_selector
    ):
        """Test that shell continues operating after query errors."""
        # First query fails
        self.setup_failing_query_mock(mock_selector, SyntaxError("Bad query"))
        assert shell_with_mocks._process_input("BadQuery") is True

        # Subsequent good query should work
        self.setup_successful_query_mock(mock_selector, [mock_wall])
        assert shell_with_mocks._process_input("IfcWall") is True

    def test_mixed_commands_and_queries_workflow(
        self, shell_with_mocks, mock_wall, mock_selector, capsys
    ):
        """Test workflow mixing commands and queries."""
        workflow = [
            ("/help", True, "command"),
            ("IfcWall", True, "query"),
            ("/help", True, "command"),
        ]

        for input_text, expected_result, input_type in workflow:
            if input_type == "query":
                self.setup_successful_query_mock(mock_selector, [mock_wall])

            result = shell_with_mocks._process_input(input_text)
            assert result == expected_result


class TestContextManagerIntegration(ShellTestBase):
    """Test using the MockIfcEnvironment context manager."""

    def test_mock_environment_successful_query(self, mock_ifc_file, capsys):
        """Test successful query using context manager."""
        mock_wall = MockSetup.create_mock_wall_entity()

        with MockIfcEnvironment(selector_return=[mock_wall]) as (
            mock_open,
            mock_selector,
        ):
            shell = IfcPeek(str(mock_ifc_file), force_interactive=True)
            shell._execute_query("IfcWall")

        assert_query_output_contains(capsys, "#1=IFCWALL('wall-guid-001'")

    def test_mock_environment_query_error(self, mock_ifc_file, capsys):
        """Test query error using context manager."""
        with MockIfcEnvironment(selector_exception=Exception("Query failed")) as (
            mock_open,
            mock_selector,
        ):
            shell = IfcPeek(str(mock_ifc_file), force_interactive=True)
            shell._execute_query("BadQuery")

        assert_error_output_contains(capsys, "IFC QUERY EXECUTION ERROR")


class TestNonInteractiveMode(ShellTestBase):
    """Test non-interactive mode with simplified setup."""

    def test_non_interactive_initialization(self, shell_non_interactive):
        """Test shell initializes properly in non-interactive mode."""
        assert shell_non_interactive.model is not None
        assert not shell_non_interactive.is_interactive
        assert shell_non_interactive.completion_cache is None
        assert shell_non_interactive.completer is None
        assert shell_non_interactive.session is None
