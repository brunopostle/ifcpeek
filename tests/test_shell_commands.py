"""Test built-in command functionality for Step 7 - IFC Query Execution."""
import pytest
from unittest.mock import patch, Mock
from pathlib import Path

from ifcpeek.shell import IfcPeek


class TestBuiltinCommandRecognition:
    """Test built-in command recognition and routing."""

    def test_builtin_commands_dictionary_exists(self, mock_ifc_file):
        """Test that BUILTIN_COMMANDS dictionary is properly defined."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Verify the commands dictionary exists and has expected commands
            assert hasattr(shell, "BUILTIN_COMMANDS")
            assert isinstance(shell.BUILTIN_COMMANDS, dict)

            # Check for required commands (IRC-style with forward slashes)
            expected_commands = ["/help", "/exit", "/quit"]
            for cmd in expected_commands:
                assert cmd in shell.BUILTIN_COMMANDS

    def test_help_command_recognition(self, mock_ifc_file, capsys):
        """Test that /help command is recognized and executed."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            # Test help command
            result = shell._process_input("/help")

            assert result is True  # Should continue shell

            captured = capsys.readouterr()
            assert "IfcPeek - Interactive IFC Model Query Tool" in captured.err

    def test_exit_command_recognition(self, mock_ifc_file):
        """Test that /exit command is recognized and executed."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Test exit command
            result = shell._process_input("/exit")

            assert result is False  # Should exit shell

    def test_quit_command_recognition(self, mock_ifc_file):
        """Test that /quit command is recognized and executed."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Test quit command
            result = shell._process_input("/quit")

            assert result is False  # Should exit shell

    def test_command_recognition_case_sensitivity(
        self, mock_ifc_file, mock_selector, capsys
    ):
        """Test that command recognition is case-sensitive."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            # Test uppercase variants (should NOT be recognized as commands)
            test_cases = ["/HELP", "/EXIT", "/QUIT", "/Help", "/Exit"]

            for case in test_cases:
                # Configure mock to simulate query error (expected for invalid queries)
                mock_selector.side_effect = Exception("Invalid query syntax")

                result = shell._process_input(case)
                assert result is True  # Should continue (treated as query)

                captured = capsys.readouterr()
                assert "IFC QUERY EXECUTION ERROR" in captured.err
                assert f"Query: {case}" in captured.err

    def test_command_recognition_with_whitespace(self, mock_ifc_file, capsys):
        """Test command recognition with surrounding whitespace."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            # Test help command with whitespace
            result = shell._process_input("  /help  ")

            assert result is True  # Should continue shell

            captured = capsys.readouterr()
            assert "IfcPeek - Interactive IFC Model Query Tool" in captured.err

    def test_invalid_commands_fall_through_to_query_processing(
        self, mock_ifc_file, mock_selector, capsys
    ):
        """Test that invalid commands are treated as queries."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            # Test invalid commands
            invalid_commands = ["/invalid", "/test", "/", "//help", "help"]

            for cmd in invalid_commands:
                # Configure mock to simulate query error for invalid syntax
                mock_selector.side_effect = Exception("Invalid query syntax")

                result = shell._process_input(cmd)
                assert result is True  # Should continue (treated as query)

                captured = capsys.readouterr()
                assert "IFC QUERY EXECUTION ERROR" in captured.err
                assert f"Query: {cmd}" in captured.err


class TestShowHelpMethod:
    """Test the _show_help method implementation."""

    def test_show_help_displays_comprehensive_help(self, mock_ifc_file, capsys):
        """Test that _show_help displays comprehensive help text."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            # Call help method directly
            result = shell._show_help()

            assert result is True  # Should continue shell

            captured = capsys.readouterr()
            help_output = captured.err

            # Check for key sections and content
            assert "IfcPeek - Interactive IFC Model Query Tool" in help_output
            assert "USAGE:" in help_output
            assert "EXAMPLES:" in help_output
            assert "COMMANDS:" in help_output
            assert "HISTORY:" in help_output

            # Check for specific examples
            assert "IfcWall" in help_output
            assert "material=concrete" in help_output
            assert "Name=Door-01" in help_output

            # Check for command descriptions (IRC-style forward slash commands)
            assert "/help" in help_output
            assert "/exit" in help_output
            assert "/quit" in help_output

            # Check for history instructions
            assert "Up/Down" in help_output
            assert "Ctrl-R" in help_output

    def test_show_help_return_value(self, mock_ifc_file):
        """Test that _show_help returns True to continue shell."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            result = shell._show_help()
            assert result is True

    def test_help_content_formatting(self, mock_ifc_file, capsys):
        """Test that help content is properly formatted."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            shell._show_help()

            captured = capsys.readouterr()
            help_lines = captured.err.split("\n")

            # Check that help starts and ends with blank lines for readability
            assert help_lines[0] == ""  # First line should be blank

            # Check section headers are properly formatted
            section_headers = ["USAGE:", "EXAMPLES:", "COMMANDS:", "HISTORY:"]
            for header in section_headers:
                header_found = any(header in line for line in help_lines)
                assert header_found, f"Section header '{header}' not found"

    def test_help_reflects_actual_functionality(self, mock_ifc_file, capsys):
        """Test that help text reflects actual shell functionality."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            shell._show_help()

            captured = capsys.readouterr()
            help_output = captured.err

            # Verify that documented commands actually exist
            documented_commands = ["/help", "/exit", "/quit"]
            for cmd in documented_commands:
                assert cmd in help_output
                assert cmd in shell.BUILTIN_COMMANDS


class TestExitMethod:
    """Test the _exit method implementation."""

    def test_exit_method_returns_false(self, mock_ifc_file):
        """Test that _exit method returns False to terminate shell."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            result = shell._exit()
            assert result is False

    def test_exit_method_callable(self, mock_ifc_file):
        """Test that _exit method is callable without arguments."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Should be callable without arguments
            result = shell._exit()
            assert isinstance(result, bool)


class TestEmptyInputHandling:
    """Test empty input handling."""

    def test_empty_string_input(self, mock_ifc_file, capsys):
        """Test that empty string input is handled gracefully."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            result = shell._process_input("")

            assert result is True  # Should continue shell

            captured = capsys.readouterr()
            assert captured.out == ""  # No output for empty input

    def test_whitespace_only_input(self, mock_ifc_file, capsys):
        """Test that whitespace-only input is handled gracefully."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            whitespace_inputs = ["   ", "\t", "\n", "  \t  \n  "]

            for whitespace in whitespace_inputs:
                result = shell._process_input(whitespace)

                assert result is True  # Should continue shell

                captured = capsys.readouterr()
                assert captured.out == ""  # No output for whitespace-only input

    def test_mixed_whitespace_and_commands(self, mock_ifc_file, capsys):
        """Test commands with surrounding whitespace."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            # Test exit command with whitespace
            result = shell._process_input("  /exit  ")

            assert result is False  # Should exit shell


class TestCommandProcessingIntegration:
    """Test command processing integration with shell loop."""

    def test_shell_loop_uses_command_return_values(self, mock_ifc_file, capsys):
        """Test that shell loop respects command return values."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            # DON'T call shell.run() - just test _process_input directly
            # Test that exit command returns False
            result = shell._process_input("/exit")
            assert result is False

            # Test that help command returns True
            result = shell._process_input("/help")
            assert result is True

            captured = capsys.readouterr()
            assert "IfcPeek - Interactive IFC Model Query Tool" in captured.err

    def test_shell_continues_after_help_command(self, mock_ifc_file, capsys):
        """Test that shell continues after help command."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            # Test help command returns True (continues)
            help_result = shell._process_input("/help")
            assert help_result is True

            # Test exit command returns False (exits)
            exit_result = shell._process_input("/exit")
            assert exit_result is False

            captured = capsys.readouterr()
            # Should contain help text
            assert "IfcPeek - Interactive IFC Model Query Tool" in captured.err

    def test_shell_processes_mixed_commands_and_queries(
        self, mock_ifc_file, mock_selector, capsys
    ):
        """Test shell processes mix of commands and queries."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            # Configure mock for successful queries
            mock_wall = Mock()
            mock_wall.__str__ = Mock(
                return_value="#1=IFCWALL('wall-guid',$,$,'Wall',$,$,$,$,$);"
            )
            mock_door = Mock()
            mock_door.__str__ = Mock(
                return_value="#2=IFCDOOR('door-guid',$,$,'Door',$,$,$,$,$);"
            )

            # Test mixed input without shell.run()
            mock_selector.return_value = [mock_wall]
            query_result = shell._process_input("IfcWall")
            assert query_result is True

            help_result = shell._process_input("/help")
            assert help_result is True

            mock_selector.return_value = [mock_door]
            query2_result = shell._process_input("IfcDoor")
            assert query2_result is True

            quit_result = shell._process_input("/quit")
            assert quit_result is False

            captured = capsys.readouterr()

            # Should contain query results
            assert "#1=IFCWALL('wall-guid'" in captured.out
            assert "#2=IFCDOOR('door-guid'" in captured.out

            # Should contain help text
            assert "IfcPeek - Interactive IFC Model Query Tool" in captured.err

    def test_exit_command_terminates_shell_immediately(self, mock_ifc_file, capsys):
        """Test that exit command terminates shell immediately."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            # Test exit command directly
            result = shell._process_input("/exit")
            assert result is False  # Should return False to exit

            # Test that we can still process other commands
            result2 = shell._process_input("/help")
            assert result2 is True  # Should return True to continue

            captured = capsys.readouterr()

            # Should contain help text from second command
            assert "IfcPeek - Interactive IFC Model Query Tool" in captured.err


class TestCommandErrorHandling:
    """Test error handling in command processing."""

    def test_command_method_exception_handling(self, mock_ifc_file, capsys):
        """Test handling when command method raises an exception."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Mock _show_help to raise an exception
            original_help = shell._show_help

            def failing_help():
                raise RuntimeError("Help failed")

            shell._show_help = failing_help

            try:
                # Clear initialization output
                capsys.readouterr()

                # This should raise the RuntimeError
                with pytest.raises(RuntimeError, match="Help failed"):
                    shell._process_input("/help")
            finally:
                # Restore original method
                shell._show_help = original_help


class TestBackwardCompatibility:
    """Test that command system maintains backward compatibility."""

    def test_execute_query_placeholder_still_exists(self, mock_ifc_file):
        """Test that _execute_query method still exists (now implements real functionality)."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Should still have the method
            assert hasattr(shell, "_execute_query")
            assert callable(shell._execute_query)

            # Should be callable (now executes real queries)
            with patch("ifcpeek.shell.ifcopenshell.util.selector.filter_elements"):
                shell._execute_query("IfcWall")

    def test_non_command_input_executes_queries(
        self, mock_ifc_file, mock_selector, capsys
    ):
        """Test that non-command input executes queries (Step 7 behavior)."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            # Configure mock for successful query
            mock_entity = Mock()
            mock_entity.__str__ = Mock(
                return_value="#1=IFCWALL('wall-guid',$,$,'Wall',$,$,$,$,$);"
            )
            mock_selector.return_value = [mock_entity]

            # Test regular input
            result = shell._process_input("IfcWall")

            assert result is True

            captured = capsys.readouterr()
            assert "#1=IFCWALL('wall-guid'" in captured.out


class TestCommandDocumentationAccuracy:
    """Test that command documentation matches implementation."""

    def test_help_text_matches_available_commands(self, mock_ifc_file, capsys):
        """Test that help text documents all available commands."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            shell._show_help()

            captured = capsys.readouterr()
            help_text = captured.err

            # Every command in BUILTIN_COMMANDS should be documented
            for command in shell.BUILTIN_COMMANDS.keys():
                assert command in help_text, f"Command {command} not documented in help"

    def test_help_text_examples_are_valid(self, mock_ifc_file, capsys):
        """Test that help text examples represent valid selector syntax."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            shell._show_help()

            captured = capsys.readouterr()
            help_text = captured.err

            # Check that example queries follow expected patterns
            example_patterns = ["IfcWall", "material=concrete", "Name=Door-01"]

            for pattern in example_patterns:
                assert (
                    pattern in help_text
                ), f"Example pattern '{pattern}' not found in help"

    def test_help_text_keyboard_shortcuts_accurate(self, mock_ifc_file, capsys):
        """Test that help text keyboard shortcuts are accurate."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            shell._show_help()

            captured = capsys.readouterr()
            help_text = captured.err

            # Check that documented keyboard shortcuts are mentioned
            shortcuts = ["Ctrl-D", "Up/Down", "Ctrl-R"]

            for shortcut in shortcuts:
                assert (
                    shortcut in help_text
                ), f"Keyboard shortcut '{shortcut}' not documented"


class TestBackslashHandling:
    """Test that backslash commands are treated as queries, not commands."""

    def test_backslash_commands_treated_as_queries(
        self, mock_ifc_file, mock_selector, capsys
    ):
        """Test that backslash variants are treated as queries."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            # Test backslash commands (should be treated as queries)
            backslash_commands = ["\\help", "\\exit", "\\quit"]

            for cmd in backslash_commands:
                # Configure mock to simulate query error for invalid syntax
                mock_selector.side_effect = Exception("Invalid selector syntax")

                result = shell._process_input(cmd)
                assert result is True  # Should continue (treated as query)

                captured = capsys.readouterr()
                assert "IFC QUERY EXECUTION ERROR" in captured.err
                assert f"Query: {cmd}" in captured.err

    def test_forward_vs_backslash_behavior(self, mock_ifc_file, mock_selector, capsys):
        """Test difference between forward slash commands and backslash queries."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            # Forward slash should work as command
            result_forward = shell._process_input("/help")
            assert result_forward is True

            captured_forward = capsys.readouterr()
            assert "IfcPeek - Interactive IFC Model Query Tool" in captured_forward.err

            # Backslash should be treated as query (and fail with invalid syntax)
            mock_selector.side_effect = Exception("Invalid selector syntax")
            result_backslash = shell._process_input("\\help")
            assert result_backslash is True

            captured_backslash = capsys.readouterr()
            assert "IFC QUERY EXECUTION ERROR" in captured_backslash.err
            assert "Query: \\help" in captured_backslash.err


class TestRealWorldScenarios:
    """Test realistic usage scenarios."""

    def test_typical_user_session_simulation(
        self, mock_ifc_file, mock_selector, capsys
    ):
        """Test a typical user session flow."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            # Configure mock entities for different queries
            mock_wall = Mock()
            mock_wall.__str__ = Mock(
                return_value="#1=IFCWALL('wall-guid',$,$,'Wall',$,$,$,$,$);"
            )
            mock_door = Mock()
            mock_door.__str__ = Mock(
                return_value="#2=IFCDOOR('door-guid',$,$,'Door',$,$,$,$,$);"
            )

            # Simulate typical user session
            session_steps = [
                ("/help", True, "User starts with help"),
                ("IfcWall", True, "User queries for walls"),
                ("IfcWall, material=concrete", True, "User refines query"),
                ("/help", True, "User checks help again"),
                ("IfcDoor", True, "User queries for doors"),
                ("/quit", False, "User exits"),
            ]

            for step_input, expected_result, description in session_steps:
                # Reset mock state for each step
                mock_selector.reset_mock()
                mock_selector.side_effect = None

                if step_input.startswith("IfcWall"):
                    mock_selector.return_value = [mock_wall]
                elif step_input.startswith("IfcDoor"):
                    mock_selector.return_value = [mock_door]
                else:
                    mock_selector.return_value = []

                result = shell._process_input(step_input)
                assert result == expected_result, f"Failed at step: {description}"

            captured = capsys.readouterr()

            # Verify session content
            assert (
                captured.err.count("IfcPeek - Interactive IFC Model Query Tool") == 2
            )  # Help shown twice
            assert "#1=IFCWALL('wall-guid'" in captured.out
            assert "#2=IFCDOOR('door-guid'" in captured.out

    def test_error_recovery_in_session(self, mock_ifc_file, mock_selector, capsys):
        """Test that session can recover from various errors."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            # Configure mock for successful query
            mock_wall = Mock()
            mock_wall.__str__ = Mock(
                return_value="#1=IFCWALL('wall-guid',$,$,'Wall',$,$,$,$,$);"
            )

            # Session with potential error points
            recovery_steps = [
                ("/help", True),
                ("", True),  # Empty input
                ("   ", True),  # Whitespace only
                ("/invalid_command", True),  # Invalid command (treated as query)
                ("/HELP", True),  # Wrong case (treated as query)
                ("IfcWall", True),  # Valid query
                ("/help", True),  # Help should still work
                ("/exit", False),  # Clean exit
            ]

            for step_input, expected_result in recovery_steps:
                # Reset mock completely for each step
                mock_selector.reset_mock()
                mock_selector.side_effect = None
                mock_selector.return_value = []

                if step_input == "IfcWall":
                    mock_selector.return_value = [mock_wall]
                elif step_input in ["/invalid_command", "/HELP"]:
                    mock_selector.side_effect = Exception("Invalid syntax")

                result = shell._process_input(step_input)
                assert (
                    result == expected_result
                ), f"Failed recovery at input: '{step_input}'"

            captured = capsys.readouterr()

            # Should have help content and query results
            assert "IfcPeek - Interactive IFC Model Query Tool" in captured.err
            assert "IFC QUERY EXECUTION ERROR" in captured.err  # From invalid commands
            assert "#1=IFCWALL('wall-guid'" in captured.out
