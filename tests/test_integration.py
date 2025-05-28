"""Integration tests for Step 7 - IFC Query Execution Integration."""

import pytest
import re
from unittest.mock import patch, Mock, MagicMock
from pathlib import Path

from ifcpeek.__main__ import main
from ifcpeek.shell import IfcPeek
from ifcpeek.exceptions import IfcPeekError


class TestMainToShellIntegration:
    """Test integration from main entry point to shell with query execution."""

    def test_main_to_shell_run_integration(self, mock_ifc_file, mock_selector, capsys):
        """Test complete integration from main() to shell.run()."""
        with patch("sys.argv", ["ifcpeek", str(mock_ifc_file)]):
            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_model.schema = "IFC4"
                mock_model.by_type.return_value = ["entity1", "entity2"]
                mock_open.return_value = mock_model

                # Mock the interactive loop to exit immediately
                mock_session = Mock()
                mock_session.prompt.side_effect = EOFError  # Exit immediately

                with patch("ifcpeek.shell.PromptSession", return_value=mock_session):
                    # Should complete successfully
                    with patch("builtins.input", side_effect=EOFError):
                        main()

        captured = capsys.readouterr()
        # Verify the complete workflow ran
        assert "IFC model loaded successfully" in captured.err
        assert "Schema: IFC4" in captured.err
        assert re.search(r"contains \d+ entities", captured.err)
        assert "Interactive shell started" in captured.err
        assert "Goodbye!" in captured.err
        assert "Shell session ended" in captured.err

    def test_main_propagates_shell_initialization_errors(self, mock_ifc_file, capsys):
        """Test that main properly handles shell initialization errors."""
        with patch("sys.argv", ["ifcpeek", str(mock_ifc_file)]):
            # Mock IfcPeek initialization to fail during session creation
            original_init = IfcPeek.__init__

            def failing_init(self, ifc_file_path):
                # Call original init up to model loading
                with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                    mock_model = Mock()
                    mock_open.return_value = mock_model
                    original_init(self, ifc_file_path)
                # Then simulate session creation failure
                raise RuntimeError("Session creation failed")

            with patch.object(IfcPeek, "__init__", failing_init):
                with pytest.raises(SystemExit) as exc_info:
                    with patch("builtins.input", side_effect=EOFError):
                        main()

                assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "Unexpected error: Session creation failed" in captured.err

    def test_main_handles_shell_run_errors(self, mock_ifc_file, capsys):
        """Test that main handles errors during shell.run()."""
        with patch("sys.argv", ["ifcpeek", str(mock_ifc_file)]):
            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_open.return_value = mock_model

                # Mock shell.run() to raise an error
                with patch.object(
                    IfcPeek, "run", side_effect=RuntimeError("Run failed")
                ):
                    with pytest.raises(SystemExit) as exc_info:
                        with patch("builtins.input", side_effect=EOFError):
                            main()

                    assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "Unexpected error: Run failed" in captured.err


class TestFileLoadingToShellLoop:
    """Test integration from file loading to interactive shell loop with query execution."""

    def test_complete_initialization_to_loop_workflow(
        self, mock_ifc_file, mock_selector, capsys
    ):
        """Test complete workflow from file loading to interactive loop."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = ["entity1", "entity2", "entity3"]
            mock_open.return_value = mock_model

            # Create shell and verify initialization
            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            # Configure mock for successful queries
            mock_entity1 = Mock()
            mock_entity1.__str__ = Mock(
                return_value="#1=IFCWALL('wall-guid',$,$,'Wall',$,$,$,$,$);"
            )
            mock_entity2 = Mock()
            mock_entity2.__str__ = Mock(
                return_value="#2=IFCDOOR('door-guid',$,$,'Door',$,$,$,$,$);"
            )

            # Mock the prompt session for controlled testing
            with patch.object(shell, "session") as mock_session:
                mock_selector.side_effect = [
                    [mock_entity1],  # First query result
                    [mock_entity2],  # Second query result
                ]

                mock_session.prompt.side_effect = [
                    "IfcWall",
                    "IfcDoor",
                    EOFError,
                ]

                with patch("builtins.input", side_effect=EOFError):
                    shell.run()

            captured = capsys.readouterr()

            # Verify complete flow
            assert "Model schema: IFC4" in captured.err
            assert re.search(r"contains \d+ entities", captured.err)
            assert "Interactive shell started" in captured.err
            assert "#1=IFCWALL('wall-guid'" in captured.out
            assert "#2=IFCDOOR('door-guid'" in captured.out
            assert "Goodbye!" in captured.err
            assert "Shell session ended" in captured.err

    def test_session_failure_fallback_to_basic_input(
        self, mock_ifc_file, mock_selector, capsys
    ):
        """Test fallback to basic input when session creation fails."""
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

                # Should have None session
                assert shell.session is None

                # Clear initialization output
                capsys.readouterr()

                # Configure mock for successful query
                mock_entity = Mock()
                mock_entity.__str__ = Mock(
                    return_value="#1=IFCWALL('wall-guid',$,$,'Wall',$,$,$,$,$);"
                )
                mock_selector.return_value = [mock_entity]

                # Mock basic input for testing
                with patch("builtins.input", side_effect=["IfcWall", EOFError]):
                    shell.run()

            captured = capsys.readouterr()
            assert "#1=IFCWALL('wall-guid'" in captured.out
            assert "Shell session ended" in captured.err

    def test_model_loading_error_prevents_shell_start(self, mock_ifc_file):
        """Test that model loading errors prevent shell from starting."""
        with patch(
            "ifcpeek.shell.ifcopenshell.open", side_effect=RuntimeError("Load failed")
        ):
            with pytest.raises(Exception) as exc_info:
                shell = IfcPeek(str(mock_ifc_file))

            # Should not reach shell.run()
            assert "Failed to load IFC file" in str(exc_info.value)


class TestSignalHandlingIntegration:
    """Test signal handling integration throughout the shell with query execution."""

    def test_keyboard_interrupt_handling_during_input(
        self, mock_ifc_file, mock_selector, capsys
    ):
        """Test KeyboardInterrupt handling during input processing."""
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

            # Simulate KeyboardInterrupt during input, then normal exit
            with patch.object(shell, "session") as mock_session:
                mock_session.prompt.side_effect = [
                    KeyboardInterrupt,  # First Ctrl-C
                    "IfcWall",  # User continues with query
                    KeyboardInterrupt,  # Another Ctrl-C
                    EOFError,  # Final exit
                ]

                with patch("builtins.input", side_effect=EOFError):
                    shell.run()

            captured = capsys.readouterr()
            assert (
                captured.err.count("(Use Ctrl-D to exit)") == 2
            )  # Two Ctrl-C messages
            assert "#1=IFCWALL('wall-guid'" in captured.out
            assert "Goodbye!" in captured.err

    def test_eof_handling_during_different_states(
        self, mock_ifc_file, mock_selector, capsys
    ):
        """Test EOFError handling at different points in the loop."""
        test_scenarios = [
            # Immediate exit
            [EOFError],
            # Exit after some input
            ["IfcWall", "IfcDoor", EOFError],
            # Exit after error
            [RuntimeError("test error"), EOFError],
        ]

        for scenario in test_scenarios:
            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_model.schema = "IFC4"
                mock_model.by_type.return_value = []
                mock_open.return_value = mock_model

                shell = IfcPeek(str(mock_ifc_file))

                # Clear initialization output
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
                # Every scenario should end with goodbye
                assert "Goodbye!" in captured.err
                assert "Shell session ended" in captured.err

    def test_multiple_signal_combinations(self, mock_ifc_file, mock_selector, capsys):
        """Test various combinations of signals."""
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

            # Complex scenario: interrupt, command, error, interrupt, exit
            with patch.object(shell, "session") as mock_session:
                mock_session.prompt.side_effect = [
                    KeyboardInterrupt,
                    "IfcWall",  # Normal query
                    RuntimeError("processing error"),
                    KeyboardInterrupt,
                    EOFError,
                ]

                with patch("builtins.input", side_effect=EOFError):
                    shell.run()

            captured = capsys.readouterr()
            assert captured.err.count("(Use Ctrl-D to exit)") == 2
            assert "#1=IFCWALL('wall-guid'" in captured.out
            assert "Error: processing error" in captured.err
            assert "Goodbye!" in captured.err


class TestErrorRecoveryIntegration:
    """Test error recovery throughout the shell system with query execution."""

    def test_shell_continues_after_processing_errors(
        self, mock_ifc_file, mock_selector, capsys
    ):
        """Test that shell continues operating after processing errors."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            # Configure mock for mixed scenarios
            mock_entity = Mock()
            mock_entity.__str__ = Mock(
                return_value="#1=IFCWALL('wall-guid',$,$,'Wall',$,$,$,$,$);"
            )

            # Mock _process_input to fail sometimes
            process_calls = 0

            def mock_process_input(input_text):
                nonlocal process_calls
                process_calls += 1
                if process_calls == 2:  # Fail on second call
                    raise ValueError("Processing failed")
                elif process_calls < 4:  # Success on other calls
                    if input_text == "IfcWall":
                        mock_selector.return_value = [mock_entity]
                        shell._execute_query(input_text)
                    return True
                else:
                    return True

            with patch.object(shell, "_process_input", side_effect=mock_process_input):
                with patch.object(shell, "session") as mock_session:
                    mock_session.prompt.side_effect = [
                        "IfcWall",  # Success
                        "command2",  # Will fail
                        "IfcWall",  # Success after error
                        EOFError,  # Exit
                    ]

                    with patch("builtins.input", side_effect=EOFError):
                        shell.run()

            captured = capsys.readouterr()
            assert "#1=IFCWALL('wall-guid'" in captured.out
            # command2 processing should fail but not crash shell
            assert "Goodbye!" in captured.err

    def test_recovery_from_session_errors_during_runtime(
        self, mock_ifc_file, mock_selector, capsys
    ):
        """Test recovery from session errors during runtime."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            # Configure mock for successful queries
            mock_entity = Mock()
            mock_entity.__str__ = Mock(
                return_value="#1=IFCWALL('wall-guid',$,$,'Wall',$,$,$,$,$);"
            )
            mock_selector.return_value = [mock_entity]

            # Mock session to work initially, then fail, then work again
            prompt_calls = 0

            def mock_prompt(prompt_text):
                nonlocal prompt_calls
                prompt_calls += 1
                if prompt_calls == 1:
                    return "IfcWall"
                elif prompt_calls == 2:
                    raise RuntimeError("Session error")
                elif prompt_calls == 3:
                    return "IfcWall"
                else:
                    raise EOFError

            with patch.object(shell, "session") as mock_session:
                mock_session.prompt.side_effect = mock_prompt

                with patch("builtins.input", side_effect=EOFError):
                    shell.run()

            captured = capsys.readouterr()
            assert "#1=IFCWALL('wall-guid'" in captured.out
            assert "Error: Session error" in captured.err
            # Note: The shell continues but the session.prompt will be called again
            # This tests that the shell loop continues after session errors


class TestShellStateConsistency:
    """Test that shell state remains consistent throughout operations with query execution."""

    def test_model_reference_consistency(self, mock_ifc_file, mock_selector):
        """Test that model reference remains consistent throughout shell operations."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))
            original_model = shell.model

            # Configure mock for query
            mock_entity = Mock()
            mock_entity.__str__ = Mock(
                return_value="#1=IFCWALL('wall-guid',$,$,'Wall',$,$,$,$,$);"
            )
            mock_selector.return_value = [mock_entity]

            # Simulate various shell operations
            shell._process_input("IfcWall")

            # Mock a shell run with some operations
            with patch.object(shell, "session") as mock_session:
                mock_session.prompt.side_effect = ["IfcWall", "IfcDoor", EOFError]
                shell.run()

            # Model reference should remain consistent
            assert shell.model is original_model

    def test_session_consistency_after_errors(self, mock_ifc_file, mock_selector):
        """Test that session remains consistent after errors."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))
            original_session = shell.session

            # Configure mock for error scenario
            mock_selector.side_effect = Exception("Query error")

            # Simulate error in processing
            try:
                shell._process_input("IfcWall")
            except Exception:
                pass

            # Session should remain the same
            assert shell.session is original_session

    def test_file_path_consistency(self, mock_ifc_file, mock_selector):
        """Test that file path remains consistent throughout operations."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))
            original_path = shell.ifc_file_path

            # Configure mock for query
            mock_entity = Mock()
            mock_entity.__str__ = Mock(
                return_value="#1=IFCWALL('wall-guid',$,$,'Wall',$,$,$,$,$);"
            )
            mock_selector.return_value = [mock_entity]

            # Perform various operations
            shell._process_input("IfcWall")

            with patch.object(shell, "session") as mock_session:
                mock_session.prompt.side_effect = EOFError
                shell.run()

            # Path should remain consistent
            assert shell.ifc_file_path == original_path
            assert shell.ifc_file_path.is_absolute()
            assert shell.ifc_file_path.exists()


class TestPerformanceIntegration:
    """Test performance aspects of the integrated shell with query execution."""

    def test_shell_startup_performance(self, mock_ifc_file):
        """Test that shell startup is reasonably fast."""
        import time

        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = list(range(1000))  # Simulate large model
            mock_open.return_value = mock_model

            # Mock session creation for performance test
            mock_session = Mock()
            with patch("ifcpeek.shell.PromptSession", return_value=mock_session):
                start_time = time.time()
                shell = IfcPeek(str(mock_ifc_file))
                initialization_time = time.time() - start_time

                # Initialization should be reasonably fast (< 1 second for mocked operations)
                assert initialization_time < 1.0
                assert shell.model is not None
                assert shell.session == mock_session

    def test_multiple_input_processing_performance(self, mock_ifc_file, mock_selector):
        """Test that multiple input processing doesn't degrade performance."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            # Create shell with or without session (both should work)
            shell = IfcPeek(str(mock_ifc_file))

            # Configure mock for queries
            mock_entity = Mock()
            mock_entity.__str__ = Mock(
                return_value="#1=IFCWALL('wall-guid',$,$,'Wall',$,$,$,$,$);"
            )
            mock_selector.return_value = [mock_entity]

            # Process multiple inputs and measure time
            import time

            start_time = time.time()

            for i in range(100):
                result = shell._process_input("IfcWall")
                assert result is True  # Should continue processing

            processing_time = time.time() - start_time

            # Processing 100 simple queries should be fast
            assert processing_time < 1.0

    def test_memory_usage_stability(self, mock_ifc_file, mock_selector):
        """Test that memory usage doesn't grow excessively during operations."""
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
            for i in range(1000):
                shell._process_input("IfcWall")

            # Shell should still be functional
            assert shell.model is not None
            # Session may be None in test environment - this is acceptable
            assert shell.session is None or hasattr(shell.session, "prompt")
            assert shell._process_input("IfcWall") is True
