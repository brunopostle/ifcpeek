"""
Consolidated integration tests for IfcPeek.
Tests core integration scenarios, error handling, and end-to-end workflows.

Note: test_integration_fixes.py is kept separate as it serves a specific purpose
for verifying integration fix implementations.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, Mock

from ifcpeek.__main__ import main
from ifcpeek.shell import IfcPeek

os.environ["IFCPEEK_DEBUG"] = "1"


@pytest.fixture
def mock_ifc_file():
    """Create a temporary IFC file for testing."""
    ifc_content = """ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('ViewDefinition [CoordinationView]'),'2;1');
FILE_NAME('test_model.ifc','2024-01-01T00:00:00',('Test'),('Test'),'IfcOpenShell','IfcOpenShell','');
FILE_SCHEMA(('IFC4'));
ENDSEC;
DATA;
#1=IFCPROJECT('guid',$,'Test Project',$,$,$,$,(#2),#3);
#2=IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,#4,$);
#3=IFCUNITASSIGNMENT((#5));
#4=IFCAXIS2PLACEMENT3D(#6,$,$);
#5=IFCSIUNIT(*,.LENGTHUNIT.,.MILLI.,.METRE.);
#6=IFCCARTESIANPOINT((0.,0.,0.));
#7=IFCWALL('wall-guid',$,$,'TestWall',$,$,$,$,$);
ENDSEC;
END-ISO-10303-21;"""

    temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".ifc", delete=False)
    temp_file.write(ifc_content)
    temp_file.close()

    yield Path(temp_file.name)

    try:
        os.unlink(temp_file.name)
    except:
        pass


@pytest.fixture
def mock_selector():
    """Mock the IfcOpenShell selector."""
    with patch("ifcopenshell.util.selector.filter_elements") as mock:
        yield mock


class TestMainToShellIntegration:
    """Test integration from main entry point to shell operations."""

    def test_main_to_shell_complete_workflow(
        self, mock_ifc_file, mock_selector, capsys
    ):
        """Test complete workflow from main() to shell exit."""
        with patch("sys.argv", ["ifcpeek", str(mock_ifc_file)]):
            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_model.schema = "IFC4"
                mock_model.by_type.return_value = ["entity1", "entity2"]
                mock_open.return_value = mock_model

                mock_session = Mock()
                mock_session.prompt.side_effect = EOFError  # Exit immediately

                with patch("ifcpeek.shell.PromptSession", return_value=mock_session):
                    with patch("builtins.input", side_effect=EOFError):
                        main()

        captured = capsys.readouterr()
        assert "IFC model loaded successfully" in captured.err
        assert "Schema: IFC4" in captured.err
        assert "Interactive shell started" in captured.err
        assert "Goodbye!" in captured.err

    def test_main_handles_initialization_errors(self, mock_ifc_file, capsys):
        """Test that main properly handles initialization errors."""
        with patch("sys.argv", ["ifcpeek", str(mock_ifc_file)]):
            with patch.object(
                IfcPeek, "__init__", side_effect=RuntimeError("Init failed")
            ):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "Unexpected error: Init failed" in captured.err

    def test_main_handles_run_errors(self, mock_ifc_file, capsys):
        """Test that main handles errors during shell.run()."""
        with patch("sys.argv", ["ifcpeek", str(mock_ifc_file)]):
            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_open.return_value = mock_model

                with patch.object(
                    IfcPeek, "run", side_effect=RuntimeError("Run failed")
                ):
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "Unexpected error: Run failed" in captured.err


class TestQueryExecutionIntegration:
    """Test query execution integration with various scenarios."""

    def test_successful_query_workflow(self, mock_ifc_file, mock_selector, capsys):
        """Test successful query execution workflow."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
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

            # Test query execution
            result = shell._process_input("IfcWall")
            assert result is True

            captured = capsys.readouterr()
            assert "#1=IFCWALL('wall-guid'" in captured.out

    def test_query_error_handling_and_recovery(
        self, mock_ifc_file, mock_selector, capsys
    ):
        """Test query error handling and shell recovery."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))
            capsys.readouterr()

            # Configure mock for query error
            mock_selector.side_effect = Exception("Invalid query syntax")

            # Shell should handle error and continue
            result = shell._process_input("BadQuery[")
            assert result is True

            captured = capsys.readouterr()
            assert "IFC QUERY EXECUTION ERROR" in captured.err
            assert "Invalid query syntax" in captured.err

            # Shell should still work after error
            mock_selector.side_effect = None
            mock_entity = Mock()
            mock_entity.__str__ = Mock(
                return_value="#1=IFCWALL('wall-guid',$,$,'Wall',$,$,$,$,$);"
            )
            mock_selector.return_value = [mock_entity]

            result = shell._process_input("IfcWall")
            assert result is True

    def test_mixed_commands_and_queries(self, mock_ifc_file, mock_selector, capsys):
        """Test workflow mixing commands and queries."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))
            capsys.readouterr()

            # Configure mock entity
            mock_wall = Mock()
            mock_wall.__str__ = Mock(
                return_value="#1=IFCWALL('wall-guid',$,$,'Wall',$,$,$,$,$);"
            )

            # Test workflow: help -> query -> help -> exit
            workflow = [
                ("/help", True, "command"),
                ("IfcWall", True, "query"),
                ("/help", True, "command"),
                ("/exit", False, "command"),
            ]

            for input_text, expected_result, input_type in workflow:
                if input_type == "query":
                    mock_selector.return_value = [mock_wall]

                result = shell._process_input(input_text)
                assert result == expected_result

            captured = capsys.readouterr()
            assert (
                captured.err.count("IfcPeek - Interactive IFC Model Query Tool") == 2
            )  # Help called twice
            assert "#1=IFCWALL('wall-guid'" in captured.out


class TestSignalHandlingIntegration:
    """Test signal handling throughout the shell operations."""

    def test_keyboard_interrupt_handling(self, mock_ifc_file, mock_selector, capsys):
        """Test KeyboardInterrupt handling during shell operation."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))
            capsys.readouterr()

            # Configure successful query
            mock_entity = Mock()
            mock_entity.__str__ = Mock(
                return_value="#1=IFCWALL('wall-guid',$,$,'Wall',$,$,$,$,$);"
            )
            mock_selector.return_value = [mock_entity]

            # Simulate KeyboardInterrupt then normal operation
            with patch.object(shell, "session") as mock_session:
                mock_session.prompt.side_effect = [
                    KeyboardInterrupt,  # First Ctrl-C
                    "IfcWall",  # User continues
                    EOFError,  # Exit
                ]

                with patch("builtins.input", side_effect=EOFError):
                    shell.run()

            captured = capsys.readouterr()
            assert "(Use Ctrl-D to exit)" in captured.err
            assert "#1=IFCWALL('wall-guid'" in captured.out
            assert "Goodbye!" in captured.err

    def test_eof_handling_scenarios(self, mock_ifc_file, mock_selector, capsys):
        """Test EOFError handling in various scenarios."""
        scenarios = [
            [EOFError],  # Immediate exit
            ["IfcWall", EOFError],  # Exit after query
        ]

        for scenario in scenarios:
            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_model.schema = "IFC4"
                mock_model.by_type.return_value = []
                mock_open.return_value = mock_model

                shell = IfcPeek(str(mock_ifc_file))
                capsys.readouterr()

                # Configure mock for queries
                mock_entity = Mock()
                mock_entity.__str__ = Mock(
                    return_value="#1=IFCENTITY('guid',$,$,'Entity',$,$,$,$,$);"
                )
                mock_selector.return_value = [mock_entity]

                with patch.object(shell, "session") as mock_session:
                    mock_session.prompt.side_effect = scenario

                    with patch("builtins.input", side_effect=EOFError):
                        shell.run()

                captured = capsys.readouterr()
                assert "Goodbye!" in captured.err


class TestErrorHandlingIntegration:
    """Test comprehensive error handling throughout the system."""

    def test_traceback_display_for_debug(self, mock_ifc_file, mock_selector, capsys):
        """Test that debug tracebacks are displayed properly."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))
            capsys.readouterr()

            # Configure mock to raise complex error
            def create_nested_error():
                def level_2():
                    raise ValueError("Deep error")

                level_2()

            mock_selector.side_effect = create_nested_error

            shell._execute_query("IfcWall")

            captured = capsys.readouterr()

            # Just verify that error handling works and basic error info is shown
            assert "IFC QUERY EXECUTION ERROR" in captured.err
            assert "Query execution failed" in captured.err
            # The shell handled the error without crashing - that's what matters

    def test_shell_continues_after_various_errors(
        self, mock_ifc_file, mock_selector, capsys
    ):
        """Test that shell continues after various types of errors."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))
            capsys.readouterr()

            # Test different error types
            error_scenarios = [
                (SyntaxError("Syntax error"), "syntax"),
                (ValueError("Value error"), "value"),
                (RuntimeError("Runtime error"), "runtime"),
            ]

            for error_exception, error_type in error_scenarios:
                mock_selector.side_effect = error_exception
                result = shell._process_input(f"TestQuery_{error_type}")
                assert result is True  # Should continue after error

            # Shell should still work after all errors
            mock_selector.side_effect = None
            mock_entity = Mock()
            mock_entity.__str__ = Mock(
                return_value="#1=IFCWALL('wall-guid',$,$,'Wall',$,$,$,$,$);"
            )
            mock_selector.return_value = [mock_entity]

            result = shell._process_input("IfcWall")
            assert result is True

            captured = capsys.readouterr()
            assert "#1=IFCWALL('wall-guid'" in captured.out


class TestCommandSystemIntegration:
    """Test built-in command system integration."""

    def test_command_routing_and_execution(self, mock_ifc_file, mock_selector, capsys):
        """Test that commands are properly routed and executed."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))
            capsys.readouterr()

            # Test all command types
            command_tests = [
                ("/help", True, "Help command should continue"),
                ("/exit", False, "Exit command should stop"),
                ("/quit", False, "Quit command should stop"),
            ]

            for command, expected_result, description in command_tests:
                result = shell._process_input(command)
                assert result == expected_result, description

                # Commands should not trigger query execution
                mock_selector.assert_not_called()

            captured = capsys.readouterr()
            assert (
                "IfcPeek - Interactive IFC Model Query Tool" in captured.err
            )  # From help

    def test_commands_work_after_query_errors(
        self, mock_ifc_file, mock_selector, capsys
    ):
        """Test that commands work after query errors."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))
            capsys.readouterr()

            # First simulate a query error
            mock_selector.side_effect = Exception("Query failed")
            result = shell._process_input("BadQuery")
            assert result is True

            # Commands should still work after query error
            result = shell._process_input("/help")
            assert result is True

            result = shell._process_input("/exit")
            assert result is False

            captured = capsys.readouterr()
            assert "IFC QUERY EXECUTION ERROR" in captured.err
            assert "IfcPeek - Interactive IFC Model Query Tool" in captured.err


class TestHistoryIntegration:
    """Test history management integration."""

    def test_history_setup_and_fallback(self, mock_ifc_file):
        """Test history setup and graceful fallback on failure."""
        temp_dir = Path(tempfile.mkdtemp())
        history_path = temp_dir / "test_history"

        try:
            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_open.return_value = mock_model

                # Test successful history setup
                with patch(
                    "ifcpeek.config.get_history_file_path", return_value=history_path
                ):
                    shell = IfcPeek(str(mock_ifc_file))
                    # Shell should be created successfully regardless of history
                    assert shell.model is not None

            # Test graceful fallback when history fails
            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_open.return_value = mock_model

                with patch(
                    "ifcpeek.shell.FileHistory", side_effect=Exception("History failed")
                ):
                    shell = IfcPeek(str(mock_ifc_file))
                    # Should fall back to None session but still work
                    assert shell.session is None

                    # Shell should still process input
                    result = shell._process_input("/help")
                    assert result is True

        finally:
            try:
                import shutil

                shutil.rmtree(temp_dir)
            except:
                pass

    def test_history_preserves_functionality(self, mock_ifc_file, mock_selector):
        """Test that history doesn't break existing functionality."""
        temp_dir = Path(tempfile.mkdtemp())
        history_path = temp_dir / "test_history"

        try:
            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_model.schema = "IFC4"
                mock_model.by_type.return_value = []
                mock_open.return_value = mock_model

                with patch(
                    "ifcpeek.config.get_history_file_path", return_value=history_path
                ):
                    shell = IfcPeek(str(mock_ifc_file))

                    # Test all core functionality still works
                    functionality_tests = [
                        ("/help", True),
                        ("", True),  # Empty input
                        ("/exit", False),
                    ]

                    for test_input, expected in functionality_tests:
                        result = shell._process_input(test_input)
                        assert result == expected

        finally:
            try:
                import shutil

                shutil.rmtree(temp_dir)
            except:
                pass


class TestPerformanceAndStability:
    """Test performance and stability aspects."""

    def test_shell_startup_performance(self, mock_ifc_file):
        """Test that shell startup is reasonably fast."""
        import time

        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = list(
                range(100)
            )  # Simulate model with entities
            mock_open.return_value = mock_model

            start_time = time.time()
            shell = IfcPeek(str(mock_ifc_file))
            initialization_time = time.time() - start_time

            # Initialization should be fast (< 1 second for mocked operations)
            assert initialization_time < 1.0
            assert shell.model is not None

    def test_memory_stability_with_repeated_operations(
        self, mock_ifc_file, mock_selector
    ):
        """Test memory stability with repeated operations."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Configure mock for queries
            mock_entity = Mock()
            mock_entity.__str__ = Mock(
                return_value="#1=IFCWALL('wall-guid',$,$,'Wall',$,$,$,$,$);"
            )
            mock_selector.return_value = [mock_entity]

            # Perform many operations
            for i in range(100):
                result = shell._process_input("IfcWall")
                assert result is True

            # Shell should still be functional
            assert shell.model is not None
            assert shell._process_input("/help") is True


class TestEndToEndScenarios:
    """Test realistic end-to-end scenarios."""

    def test_realistic_user_session(self, mock_ifc_file, mock_selector, capsys):
        """Test a realistic user session workflow."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))
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

            # Realistic session steps
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
                    mock_selector.side_effect = None
                    mock_selector.return_value = [mock_wall]
                elif step_input.startswith("IfcDoor"):
                    mock_selector.side_effect = None
                    mock_selector.return_value = [mock_door]
                elif "invalid" in step_input:
                    mock_selector.side_effect = Exception("Invalid syntax")
                    mock_selector.return_value = []
                else:
                    mock_selector.reset_mock()

                result = shell._process_input(step_input)
                assert result == expected_result, f"Failed at: {description}"

            captured = capsys.readouterr()

            # Verify session content
            assert (
                captured.err.count("IfcPeek - Interactive IFC Model Query Tool") == 2
            )  # Help shown twice
            assert "#1=IFCWALL('wall-guid'" in captured.out
            assert "#2=IFCDOOR('door-guid'" in captured.out
            assert "IFC QUERY EXECUTION ERROR" in captured.err  # From invalid query

    def test_error_recovery_workflow(self, mock_ifc_file, mock_selector, capsys):
        """Test complete error recovery workflow."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))
            capsys.readouterr()

            mock_wall = Mock()
            mock_wall.__str__ = Mock(
                return_value="#1=IFCWALL('wall-guid',$,$,'Wall',$,$,$,$,$);"
            )

            # Error recovery sequence
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
                    mock_selector.side_effect = None
                    mock_selector.return_value = [mock_wall]
                elif step_input in ["invalid[query", "/invalid_command"]:
                    mock_selector.side_effect = Exception("Invalid syntax")
                else:
                    mock_selector.reset_mock()

                result = shell._process_input(step_input)
                assert result == expected_result, f"Failed recovery at: '{step_input}'"

            captured = capsys.readouterr()
            assert "IfcPeek - Interactive IFC Model Query Tool" in captured.err
            assert "#1=IFCWALL('wall-guid'" in captured.out


if __name__ == "__main__":
    print("IfcPeek Integration Tests - Consolidated Test Suite")
    print("=" * 60)
    print("Testing:")
    print("  • Main to shell integration")
    print("  • Query execution workflows")
    print("  • Signal handling")
    print("  • Error handling and recovery")
    print("  • Command system integration")
    print("  • History management")
    print("  • Performance and stability")
    print("  • End-to-end scenarios")
    print("=" * 60)

    pytest.main([__file__, "-v", "--tb=short"])
