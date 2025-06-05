"""Simplified integration tests with minimal setup duplication."""

import pytest
from unittest.mock import patch

try:
    from ifcpeek.__main__ import main
    from ifcpeek.shell import IfcPeek
except ImportError:
    import sys

    sys.path.insert(0, "src")
    from ifcpeek.__main__ import main

try:
    from .test_utils import (
        ShellTestBase,
        QueryTestMixin,
        MockIfcEnvironment,
        MockSetup,
        assert_query_output_contains,
        assert_error_output_contains,
    )
except ImportError:
    from test_utils import (
        ShellTestBase,
        QueryTestMixin,
        MockIfcEnvironment,
        MockSetup,
        assert_query_output_contains,
        assert_error_output_contains,
    )


class TestMainToShellIntegration(ShellTestBase):
    """Test integration from main entry point to shell operations."""

    def test_main_to_shell_complete_workflow(self, mock_ifc_file, capsys):
        """Test complete workflow from main() to shell exit."""
        mock_wall = MockSetup.create_mock_wall_entity()

        with patch("sys.argv", ["ifcpeek", str(mock_ifc_file), "--force-interactive"]):
            with MockIfcEnvironment(selector_return=[mock_wall]) as (
                mock_open,
                mock_selector,
            ):
                with patch("ifcpeek.shell.PromptSession") as mock_session_class:
                    mock_session = mock_session_class.return_value
                    mock_session.prompt.side_effect = EOFError  # Exit immediately

                    main()

        captured = capsys.readouterr()
        assert "IFC model loaded successfully" in captured.err
        assert "IfcPeek starting" in captured.err
        assert "Goodbye!" in captured.err

    def test_main_handles_initialization_errors(self, mock_ifc_file, capsys):
        """Test that main properly handles initialization errors."""
        with patch("sys.argv", ["ifcpeek", str(mock_ifc_file)]):
            with patch(
                "ifcpeek.__main__.IfcPeek", side_effect=RuntimeError("Init failed")
            ):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 1

        assert_error_output_contains(capsys, "Unexpected error: Init failed")


class TestQueryExecutionIntegration(ShellTestBase, QueryTestMixin):
    """Test query execution integration with various scenarios."""

    def test_successful_query_workflow(
        self, shell_with_mocks, mock_wall, mock_selector, capsys
    ):
        """Test successful query execution workflow."""
        self.setup_successful_query_mock(mock_selector, [mock_wall])

        result = shell_with_mocks._process_input("IfcWall")
        assert result is True

        assert_query_output_contains(capsys, "#1=IFCWALL('wall-guid-001'")

    def test_query_error_handling_and_recovery(
        self, shell_with_mocks, mock_wall, mock_selector, capsys
    ):
        """Test query error handling and shell recovery."""
        # First query fails
        self.setup_failing_query_mock(mock_selector, Exception("Invalid query syntax"))
        assert shell_with_mocks._process_input("BadQuery[") is True

        assert_error_output_contains(capsys, "IFC QUERY EXECUTION ERROR")

        # Shell should still work after error
        capsys.readouterr()  # Clear previous output
        self.setup_successful_query_mock(mock_selector, [mock_wall])
        assert shell_with_mocks._process_input("IfcWall") is True

    def test_mixed_commands_and_queries(
        self, shell_with_mocks, mock_wall, mock_selector, capsys
    ):
        """Test workflow mixing commands and queries."""
        workflow = [
            ("/help", True, "command"),
            ("IfcWall", True, "query"),
            ("/help", True, "command"),
            ("/exit", False, "command"),
        ]

        for input_text, expected_result, input_type in workflow:
            if input_type == "query":
                self.setup_successful_query_mock(mock_selector, [mock_wall])

            result = shell_with_mocks._process_input(input_text)
            assert result == expected_result

        captured = capsys.readouterr()
        assert (
            captured.err.count("IfcPeek - Interactive IFC Model Query Tool") == 2
        )  # Help called twice
        assert "#1=IFCWALL('wall-guid-001'" in captured.out


class TestSignalHandlingIntegration(ShellTestBase):
    """Test signal handling throughout the shell operations."""

    def test_keyboard_interrupt_handling(
        self, shell_with_mocks, mock_wall, mock_selector, capsys
    ):
        """Test KeyboardInterrupt handling during shell operation."""
        self.setup_successful_query_mock(mock_selector, [mock_wall])

        # Simulate KeyboardInterrupt then normal operation
        with patch.object(shell_with_mocks, "session") as mock_session:
            mock_session.prompt.side_effect = [
                KeyboardInterrupt,  # First Ctrl-C
                "IfcWall",  # User continues
                EOFError,  # Exit
            ]

            with patch("builtins.input", side_effect=EOFError):
                shell_with_mocks.run()

        captured = capsys.readouterr()
        assert "(Use Ctrl-D to exit)" in captured.err
        assert "#1=IFCWALL('wall-guid-001'" in captured.out
        assert "Goodbye!" in captured.err

    def setup_successful_query_mock(self, mock_selector, entities):
        """Helper method for setting up successful query mock."""
        mock_selector.return_value = entities
        mock_selector.side_effect = None


class TestErrorHandlingIntegration(ShellTestBase):
    """Test comprehensive error handling throughout the system."""

    def test_shell_continues_after_various_errors(
        self, shell_with_mocks, mock_wall, mock_selector
    ):
        """Test that shell continues operating after various types of errors."""
        error_scenarios = [
            (SyntaxError("Syntax error"), "syntax"),
            (ValueError("Value error"), "value"),
            (RuntimeError("Runtime error"), "runtime"),
        ]

        for error_exception, error_type in error_scenarios:
            mock_selector.side_effect = error_exception
            assert shell_with_mocks._process_input(f"TestQuery_{error_type}") is True

        # Shell should still work after all errors
        mock_selector.side_effect = None
        mock_selector.return_value = [mock_wall]
        assert shell_with_mocks._process_input("IfcWall") is True


class TestEndToEndScenarios(ShellTestBase, QueryTestMixin):
    """Test realistic end-to-end scenarios."""

    def test_realistic_user_session(
        self, shell_with_mocks, mock_wall, mock_door, mock_selector, capsys
    ):
        """Test a realistic user session workflow."""
        session_steps = [
            ("/help", True, "User starts with help"),
            ("IfcWall", True, "User queries for walls"),
            ("IfcWall, material=concrete", True, "User refines query"),
            ("invalid[query", True, "User makes error"),
            ("/help", True, "User checks help again"),
            ("IfcDoor", True, "User queries for doors"),
            ("/exit", False, "User exits"),
        ]

        for step_input, expected_result, description in session_steps:
            if step_input.startswith("IfcWall"):
                self.setup_successful_query_mock(mock_selector, [mock_wall])
            elif step_input.startswith("IfcDoor"):
                self.setup_successful_query_mock(mock_selector, [mock_door])
            elif "invalid" in step_input:
                self.setup_failing_query_mock(
                    mock_selector, Exception("Invalid syntax")
                )
            else:
                mock_selector.reset_mock()

            result = shell_with_mocks._process_input(step_input)
            assert result == expected_result, f"Failed at: {description}"

        captured = capsys.readouterr()

        # Verify session content
        assert (
            captured.err.count("IfcPeek - Interactive IFC Model Query Tool") == 2
        )  # Help shown twice
        assert "#1=IFCWALL('wall-guid-001'" in captured.out
        assert "#2=IFCDOOR('door-guid-001'" in captured.out
        assert "IFC QUERY EXECUTION ERROR" in captured.err  # From invalid query

    def test_error_recovery_workflow(
        self, shell_with_mocks, mock_wall, mock_selector, capsys
    ):
        """Test complete error recovery workflow."""
        recovery_steps = [
            ("/help", True),
            ("", True),  # Empty input
            ("   ", True),  # Whitespace
            ("invalid[query", True),  # Invalid query
            ("/invalid_command", True),  # Invalid command (treated as query)
            ("IfcWall", True),  # Valid query
            ("/help", True),  # Help should still work
            ("/exit", False),  # Clean exit
        ]

        for step_input, expected_result in recovery_steps:
            if step_input == "IfcWall":
                self.setup_successful_query_mock(mock_selector, [mock_wall])
            elif step_input in ["invalid[query", "/invalid_command"]:
                self.setup_failing_query_mock(
                    mock_selector, Exception("Invalid syntax")
                )
            else:
                mock_selector.reset_mock()

            result = shell_with_mocks._process_input(step_input)
            assert result == expected_result, f"Failed recovery at: '{step_input}'"

        captured = capsys.readouterr()
        assert "IfcPeek - Interactive IFC Model Query Tool" in captured.err
        assert "#1=IFCWALL('wall-guid-001'" in captured.out


class TestPerformanceAndStability(ShellTestBase):
    """Test performance and stability aspects."""

    def test_shell_startup_performance(self, mock_ifc_file):
        """Test that shell startup is reasonably fast."""
        import time
        from ifcpeek.shell import IfcPeek  # Import here to avoid module-level issues

        mock_model = MockSetup.create_mock_model()
        # Simulate model with entities for more realistic test
        mock_model.by_type.return_value = list(range(100))

        with patch("ifcpeek.shell.ifcopenshell.open", return_value=mock_model):
            start_time = time.time()
            shell = IfcPeek(str(mock_ifc_file), force_interactive=True)
            initialization_time = time.time() - start_time

            # Initialization should be fast (< 1 second for mocked operations)
            assert initialization_time < 1.0
            assert shell.model is not None

    def test_memory_stability_with_repeated_operations(
        self, shell_with_mocks, mock_wall, mock_selector
    ):
        """Test memory stability with repeated operations."""
        self.setup_successful_query_mock(mock_selector, [mock_wall])

        # Perform many operations
        for i in range(100):
            result = shell_with_mocks._process_input("IfcWall")
            assert result is True

        # Shell should still be functional
        assert shell_with_mocks.model is not None
        assert shell_with_mocks._process_input("/help") is True


# Helper method for ShellTestBase
def setup_successful_query_mock(self, mock_selector, entities):
    """Helper method to setup successful query mock."""
    mock_selector.return_value = entities
    mock_selector.side_effect = None


# Add helper method to ShellTestBase
ShellTestBase.setup_successful_query_mock = setup_successful_query_mock
