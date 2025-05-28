"""Integration tests for Step 7 - Built-in Commands Integration with Query Execution."""

import pytest
from unittest.mock import patch, Mock

from ifcpeek.__main__ import main
from ifcpeek.shell import IfcPeek


class TestMainToCommandsIntegration:
    """Test integration from main entry point through command processing with query execution."""

    def test_main_can_import_shell_with_commands(self, mock_ifc_file):
        """Test that main can import shell and shell has command system."""
        # Test that imports work correctly
        from ifcpeek.shell import IfcPeek

        # Test that IfcPeek has command system when instantiated
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Verify command system is present
            assert hasattr(shell, "BUILTIN_COMMANDS")
            assert "/help" in shell.BUILTIN_COMMANDS
            assert "/exit" in shell.BUILTIN_COMMANDS
            assert "/quit" in shell.BUILTIN_COMMANDS

    def test_shell_command_integration_without_main(
        self, mock_ifc_file, mock_selector, capsys
    ):
        """Test shell command integration without calling main()."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            # Test complete workflow: help -> query -> exit
            help_result = shell._process_input("/help")
            assert help_result is True

            # Configure mock for successful query
            mock_entity = Mock()
            mock_entity.__str__ = Mock(
                return_value="#1=IFCWALL('wall-guid',$,$,'Wall',$,$,$,$,$);"
            )
            mock_selector.return_value = [mock_entity]

            query_result = shell._process_input("IfcWall")
            assert query_result is True

            exit_result = shell._process_input("/exit")
            assert exit_result is False

            captured = capsys.readouterr()

            # Verify complete workflow
            assert "IfcPeek - Interactive IFC Model Query Tool" in captured.err
            assert "#1=IFCWALL('wall-guid'" in captured.out

    def test_argument_parsing_integration(self):
        """Test that argument parsing works with command system."""
        from unittest.mock import patch

        # Test that main accepts IFC file argument (without actually running)
        test_args = ["ifcpeek", "test.ifc"]

        with patch("sys.argv", test_args):
            with patch("ifcpeek.__main__.IfcPeek") as mock_shell_class:
                mock_shell = Mock()
                mock_shell_class.return_value = mock_shell

                # Mock shell.run to avoid hanging
                mock_shell.run = Mock()

                # This should not raise an exception
                main()

                # Verify IfcPeek was instantiated with correct file
                mock_shell_class.assert_called_once_with("test.ifc")
                mock_shell.run.assert_called_once()


class TestCommandProcessingWithErrorRecovery:
    """Test command processing with error recovery scenarios with query execution."""

    def test_commands_work_after_input_errors(
        self, mock_ifc_file, mock_selector, capsys
    ):
        """Test that commands work after input processing errors."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            # Simulate an error scenario then test command recovery
            try:
                # This should work normally
                result1 = shell._process_input("/help")
                assert result1 is True

                # Simulate a query that causes an error
                mock_selector.side_effect = Exception("Query failed")
                result2 = shell._process_input("invalid query")
                assert result2 is True

                # Command should still work after query error
                result3 = shell._process_input("/exit")
                assert result3 is False

            except Exception as e:
                pytest.fail(f"Commands should work after errors: {e}")

            captured = capsys.readouterr()
            assert "IfcPeek - Interactive IFC Model Query Tool" in captured.err
            assert "IFC QUERY EXECUTION ERROR" in captured.err

    def test_command_consistency_across_operations(self, mock_ifc_file, mock_selector):
        """Test that commands remain consistent across various operations."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Store original command dictionary
            original_commands = dict(shell.BUILTIN_COMMANDS)

            # Configure mock for queries
            mock_entity = Mock()
            mock_entity.__str__ = Mock(
                return_value="#1=IFCWALL('wall-guid',$,$,'Wall',$,$,$,$,$);"
            )

            # Perform various operations
            operations = [
                "/help",
                "IfcWall",
                "/help",
                "IfcDoor, Name=TestDoor",
                "/quit",
            ]

            expected_results = [True, True, True, True, False]

            for operation, expected in zip(operations, expected_results):
                if operation.startswith("Ifc"):
                    # Configure mock for IFC queries
                    mock_selector.return_value = [mock_entity]
                    mock_selector.side_effect = None

                result = shell._process_input(operation)
                assert (
                    result == expected
                ), f"Operation '{operation}' returned {result}, expected {expected}"

            # Command dictionary should remain unchanged
            assert shell.BUILTIN_COMMANDS == original_commands


class TestCommandFallbackBehavior:
    """Test command behavior in fallback scenarios with query execution."""

    def test_commands_work_without_prompt_session(self, mock_ifc_file, capsys):
        """Test that commands work when prompt session creation fails."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            # Force session creation to fail
            with patch(
                "ifcpeek.shell.PromptSession", side_effect=Exception("Session failed")
            ):
                shell = IfcPeek(str(mock_ifc_file))

                # Should have None session but commands should still work
                assert shell.session is None

                # Clear initialization output
                capsys.readouterr()

                # Commands should work even without prompt session
                help_result = shell._process_input("/help")
                assert help_result is True

                exit_result = shell._process_input("/exit")
                assert exit_result is False

                captured = capsys.readouterr()
                assert "IfcPeek - Interactive IFC Model Query Tool" in captured.err

    def test_model_operations_dont_affect_commands(self, mock_ifc_file, mock_selector):
        """Test that model operations don't affect command processing."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = ["entity1", "entity2"]
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Configure mock for queries
            mock_entity = Mock()
            mock_entity.__str__ = Mock(
                return_value="#1=IFCWALL('wall-guid',$,$,'Wall',$,$,$,$,$);"
            )
            mock_selector.return_value = [mock_entity]

            # Perform some model operations (simulated)
            entities = shell.model.by_type("IfcRoot")
            assert len(entities) == 2

            # Execute some queries
            shell._process_input("IfcWall")

            # Commands should still work after model operations
            result = shell._process_input("/help")
            assert result is True

            result = shell._process_input("/quit")
            assert result is False


class TestCommandSystemConsistency:
    """Test consistency of command system across different scenarios with query execution."""

    def test_command_mapping_consistency(self, mock_ifc_file):
        """Test that command mappings are consistent and functional."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Verify all commands in mapping have corresponding methods
            for command, method_name in shell.BUILTIN_COMMANDS.items():
                assert hasattr(
                    shell, method_name
                ), f"Method {method_name} not found for command {command}"
                method = getattr(shell, method_name)
                assert callable(method), f"Method {method_name} is not callable"

                # Test that method returns boolean
                result = method()
                assert isinstance(
                    result, bool
                ), f"Method {method_name} should return bool"

    def test_command_return_value_consistency(self, mock_ifc_file):
        """Test that all command methods return consistent boolean values."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Test all command methods return boolean
            for command, method_name in shell.BUILTIN_COMMANDS.items():
                method = getattr(shell, method_name)
                result = method()
                assert isinstance(
                    result, bool
                ), f"Method {method_name} returned {type(result)}, expected bool"

                # Help should return True, exits should return False
                if method_name == "_show_help":
                    assert result is True, "Help command should return True"
                elif method_name == "_exit":
                    assert result is False, "Exit command should return False"

    def test_exit_commands_equivalence(self, mock_ifc_file):
        """Test that both /exit and /quit commands work identically."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Test both exit commands
            exit_result = shell._process_input("/exit")
            quit_result = shell._process_input("/quit")

            # Both should return False (exit shell)
            assert exit_result is False
            assert quit_result is False
            assert exit_result == quit_result

    def test_help_command_idempotency(self, mock_ifc_file, capsys):
        """Test that help command can be called multiple times consistently."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            # Call help multiple times
            results = []
            for i in range(3):
                result = shell._process_input("/help")
                results.append(result)
                capsys.readouterr()  # Clear output between calls

            # All calls should return True and be consistent
            assert all(result is True for result in results)
            assert len(set(results)) == 1  # All results should be identical


class TestCommandSystemPerformance:
    """Test performance aspects of command system with query execution."""

    def test_command_recognition_performance(self, mock_ifc_file):
        """Test that command recognition is fast."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            import time

            # Test many command recognitions
            start_time = time.time()

            for _ in range(100):  # Reduced from 1000 to avoid excessive test time
                shell._process_input("/help")

            elapsed_time = time.time() - start_time

            # Should be fast (< 1 second for 100 operations)
            assert elapsed_time < 1.0

    def test_large_input_handling_with_commands(self, mock_ifc_file, mock_selector):
        """Test handling of various input sizes with command system."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Test various input scenarios
            test_inputs = [
                "/help",  # Normal command
                "/help" + " " * 100,  # Command with lots of whitespace
                "IfcWall" + "x" * 1000,  # Long query (would fail but shell handles it)
                "/exit",  # Normal exit
            ]

            expected_results = [True, True, True, False]

            for test_input, expected in zip(test_inputs, expected_results):
                if "IfcWall" in test_input:
                    # Configure mock for the query (will likely fail due to invalid syntax)
                    mock_selector.side_effect = Exception("Invalid syntax")
                else:
                    mock_selector.side_effect = None
                    mock_selector.return_value = []

                result = shell._process_input(test_input)
                assert result == expected


class TestCommandSystemEdgeCases:
    """Test edge cases in command system with query execution."""

    def test_command_with_various_whitespace_patterns(self, mock_ifc_file):
        """Test commands with different whitespace patterns."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Test various whitespace patterns
            whitespace_tests = [
                ("  /help  ", True),  # Spaces around
                ("\t/help\t", True),  # Tabs around
                (" \t /help \t ", True),  # Mixed whitespace
                ("  /exit  ", False),  # Exit with spaces
                ("\t/quit\t", False),  # Quit with tabs
            ]

            for test_input, expected in whitespace_tests:
                result = shell._process_input(test_input)
                assert (
                    result == expected
                ), f"Input '{repr(test_input)}' gave {result}, expected {expected}"

    def test_unicode_and_special_characters(self, mock_ifc_file, mock_selector, capsys):
        """Test handling of Unicode and special characters."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            # Test Unicode characters (should be treated as queries)
            unicode_tests = ["/帮助", "/помощь", "/🆘"]

            for unicode_input in unicode_tests:
                # Configure mock to simulate query error for invalid syntax
                mock_selector.side_effect = Exception("Invalid selector syntax")

                result = shell._process_input(unicode_input)
                assert result is True  # Should be treated as query

                captured = capsys.readouterr()
                assert "IFC QUERY EXECUTION ERROR" in captured.err
                assert f"Query: {unicode_input}" in captured.err

    def test_empty_and_none_edge_cases(self, mock_ifc_file, capsys):
        """Test edge cases with empty input."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            # Test empty and whitespace inputs
            edge_cases = ["", "   ", "\t", "\n", "  \t\n  "]

            for edge_case in edge_cases:
                result = shell._process_input(edge_case)
                assert result is True  # Should continue

                captured = capsys.readouterr()
                assert captured.out == ""  # No output for empty input


class TestRealWorldScenarios:
    """Test realistic usage scenarios with query execution."""

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
                # Reset mock state for each step
                mock_selector.reset_mock()
                mock_selector.side_effect = None

                if step_input == "IfcWall":
                    mock_selector.return_value = [mock_wall]
                elif step_input in ["/invalid_command", "/HELP"]:
                    mock_selector.side_effect = Exception("Invalid syntax")
                    mock_selector.return_value = []
                else:
                    mock_selector.return_value = []

                result = shell._process_input(step_input)
                assert (
                    result == expected_result
                ), f"Failed recovery at input: '{step_input}'"

            captured = capsys.readouterr()

            # Should have help content and query results
            assert "IfcPeek - Interactive IFC Model Query Tool" in captured.err
            assert "IFC QUERY EXECUTION ERROR" in captured.err  # From invalid commands
            assert "#1=IFCWALL('wall-guid'" in captured.out


class TestCommandQueryIntegration:
    """Test integration between commands and query execution."""

    def test_commands_bypass_query_execution(self, mock_ifc_file, mock_selector):
        """Test that built-in commands bypass query execution entirely."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Test all built-in commands
            commands_to_test = ["/help", "/exit", "/quit"]

            for command in commands_to_test:
                # Reset mock call count
                mock_selector.reset_mock()

                # Execute command
                result = shell._process_input(command)

                # Verify behavior
                if command == "/help":
                    assert result is True
                else:  # /exit or /quit
                    assert result is False

                # Most importantly: query execution should NOT be called
                mock_selector.assert_not_called()

    def test_non_commands_execute_queries(self, mock_ifc_file, mock_selector, capsys):
        """Test that non-command input executes queries."""
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

            # Test non-command input
            non_commands = ["IfcWall", "IfcDoor", "random text", "123"]

            for input_text in non_commands:
                mock_selector.reset_mock()
                mock_selector.side_effect = None

                if input_text.startswith("Ifc"):
                    # Valid IFC queries should succeed
                    mock_selector.return_value = [mock_entity]
                else:
                    # Invalid queries should fail
                    mock_selector.side_effect = Exception("Invalid syntax")
                    mock_selector.return_value = []

                result = shell._process_input(input_text)
                assert result is True  # Should continue

                # Query execution SHOULD be called
                mock_selector.assert_called_once_with(mock_model, input_text)

            captured = capsys.readouterr()
            # Should have both successful query results and error messages
            assert "#1=IFCWALL('wall-guid'" in captured.out
            assert "IFC QUERY EXECUTION ERROR" in captured.err

    def test_mixed_commands_and_queries_workflow(
        self, mock_ifc_file, mock_selector, capsys
    ):
        """Test realistic workflow mixing commands and queries."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            # Configure mock entities
            mock_wall = Mock()
            mock_wall.__str__ = Mock(
                return_value="#1=IFCWALL('wall-guid',$,$,'Wall',$,$,$,$,$);"
            )
            mock_door = Mock()
            mock_door.__str__ = Mock(
                return_value="#2=IFCDOOR('door-guid',$,$,'Door',$,$,$,$,$);"
            )

            # Realistic workflow
            workflow = [
                ("/help", "command"),  # User checks help
                ("IfcWall", "query"),  # User queries for walls
                ("/help", "command"),  # User checks help again
                ("IfcDoor", "query"),  # User queries for doors
                ("invalid", "query"),  # User makes invalid query
                ("/exit", "command"),  # User exits
            ]

            for input_text, input_type in workflow:
                # Reset mock state for each step
                mock_selector.reset_mock()
                mock_selector.side_effect = None

                if input_type == "query":
                    if input_text == "IfcWall":
                        mock_selector.return_value = [mock_wall]
                    elif input_text == "IfcDoor":
                        mock_selector.return_value = [mock_door]
                    else:
                        mock_selector.side_effect = Exception("Invalid syntax")
                        mock_selector.return_value = []

                result = shell._process_input(input_text)

                # Commands and queries should have appropriate return values
                if input_text == "/exit":
                    assert result is False
                else:
                    assert result is True

            captured = capsys.readouterr()

            # Verify complete workflow output
            assert (
                captured.err.count("IfcPeek - Interactive IFC Model Query Tool") == 2
            )  # Help called twice
            assert "#1=IFCWALL('wall-guid'" in captured.out
            assert "#2=IFCDOOR('door-guid'" in captured.out
            assert "IFC QUERY EXECUTION ERROR" in captured.err  # From invalid query
