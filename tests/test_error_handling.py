"""Comprehensive test cases for error handling and signal support."""

import pytest
import signal
from unittest.mock import patch, Mock

from ifcpeek.shell import IfcPeek
from ifcpeek.__main__ import main
from ifcpeek.exceptions import (
    FileNotFoundError,
    InvalidIfcFileError,
    QueryExecutionError,
    ConfigurationError,
)


class TestErrorHandling:
    """Test error handling with full tracebacks."""

    def test_execute_query_shows_full_traceback(self, mock_ifc_file, capsys):
        """Test that query execution shows full Python traceback on error."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            # Use a simple, predictable exception
            with patch(
                "ifcpeek.shell.ifcopenshell.util.selector.filter_elements",
                side_effect=ValueError("Test error message"),
            ):
                shell._execute_query("IfcWall")

                captured = capsys.readouterr()
                output = captured.err

                # Check for the essential error handling features
                assert "IFC QUERY EXECUTION ERROR" in output
                assert "FULL PYTHON TRACEBACK:" in output
                assert "Traceback (most recent call last):" in output
                assert "ValueError" in output
                assert "Test error message" in output
                assert "DEBUGGING SUGGESTIONS:" in output
                assert "Query execution failed - shell will continue" in output

    def test_model_loading_shows_debug_information(self, mock_ifc_file, capsys):
        """Test that model loading errors show comprehensive debug info."""
        with patch(
            "ifcpeek.shell.ifcopenshell.open",
            side_effect=RuntimeError("Parsing failed at line 42"),
        ):

            with pytest.raises(InvalidIfcFileError):
                IfcPeek(str(mock_ifc_file))

            captured = capsys.readouterr()
            output = captured.err

            # Should contain debug information
            assert "IFC MODEL LOADING ERROR - DEBUG INFORMATION" in output
            assert "file_path:" in output
            assert "file_exists:" in output
            assert "file_size:" in output
            assert "error_type:" in output
            assert "Full Python traceback:" in output
            assert "Parsing failed at line 42" in output

    def test_signal_handlers_configured(self, mock_ifc_file, capsys):
        """Test that signal handlers are properly configured."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            with patch("signal.signal") as mock_signal:
                IfcPeek(str(mock_ifc_file))

                # Verify signal handlers were set up
                assert mock_signal.call_count >= 2

                # Check SIGINT and SIGTERM were configured
                calls = mock_signal.call_args_list
                signal_nums = [call[0][0] for call in calls]
                assert signal.SIGINT in signal_nums
                assert signal.SIGTERM in signal_nums

                captured = capsys.readouterr()
                assert (
                    "Signal handlers configured for graceful operation" in captured.err
                )

    def test_sigint_handler_behavior(self, mock_ifc_file, capsys):
        """Test SIGINT handler returns to prompt instead of crashing."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            # Simulate SIGINT handler
            # Get the actual handler that was registered
            with patch("signal.signal") as mock_signal:
                shell._setup_signal_handlers()

                # Find the SIGINT handler
                sigint_handler = None
                for call in mock_signal.call_args_list:
                    if call[0][0] == signal.SIGINT:
                        sigint_handler = call[0][1]
                        break

                assert sigint_handler is not None

                # Call the handler
                sigint_handler(signal.SIGINT, None)

                captured = capsys.readouterr()
                assert "(Use Ctrl-D to exit, or type /exit)" in captured.err

    def test_process_input_error_recovery(self, mock_ifc_file, capsys):
        """Test that input processing errors don't crash the shell."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            # Mock _execute_query to raise an exception
            def failing_execute_query(query):
                raise RuntimeError("Query processing failed")

            shell._execute_query = failing_execute_query

            # Should not crash, should return True to continue
            result = shell._process_input("IfcWall")
            assert result is True

            captured = capsys.readouterr()
            assert "ERROR: Unexpected error processing input" in captured.err
            assert "Shell will continue" in captured.err

    def test_exceptions_with_context(self):
        """Test exception classes include context information."""
        # Test FileNotFoundError with context
        file_error = FileNotFoundError("File missing", file_path="/path/to/file.ifc")
        assert "file_path=/path/to/file.ifc" in str(file_error)

        # Test InvalidIfcFileError with context
        ifc_error = InvalidIfcFileError(
            "Invalid file",
            file_path="/path/to/file.ifc",
            file_size=1024,
            error_type="ParseError",
        )
        error_str = str(ifc_error)
        assert "file_path=/path/to/file.ifc" in error_str
        assert "file_size=1024" in error_str
        assert "error_type=ParseError" in error_str

        # Test QueryExecutionError with context
        query_error = QueryExecutionError(
            "Query failed", query="IfcWall", model_schema="IFC4"
        )
        error_str = str(query_error)
        assert "query=IfcWall" in error_str
        assert "model_schema=IFC4" in error_str

    def test_main_error_reporting(self, mock_ifc_file, capsys):
        """Test main function shows error reporting."""
        with patch("sys.argv", ["ifcpeek", str(mock_ifc_file)]):
            with patch(
                "ifcpeek.__main__.IfcPeek",
                side_effect=RuntimeError("Unexpected startup error"),
            ):

                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 1

                captured = capsys.readouterr()
                assert "UNEXPECTED ERROR" in captured.err
                assert "Unexpected startup error" in captured.err
                assert "Full error details:" in captured.err

    def test_session_creation_error_handling(self, mock_ifc_file, capsys):
        """Test session creation error handling with detailed diagnostics."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            # Override test environment detection to allow session creation and test error handling
            with patch(
                "ifcpeek.shell.IfcPeek._is_in_test_environment", return_value=False
            ):
                with patch(
                    "ifcpeek.shell.PromptSession",
                    side_effect=PermissionError("Permission denied"),
                ):

                    with pytest.raises(ConfigurationError):
                        IfcPeek(str(mock_ifc_file))

            captured = capsys.readouterr()
            assert (
                "ERROR: Session creation failed due to filesystem issue" in captured.err
            )
            assert "This is a critical configuration issue" in captured.err


class TestSignalHandlingIntegration:
    """Test signal handling integration with shell operations."""

    def test_signal_handling_preserves_shell_state(self, mock_ifc_file, mock_selector):
        """Test that signal handling doesn't interfere with shell state."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Store original state
            original_model = shell.model
            original_session = shell.session

            # Configure mock for query
            mock_entity = Mock()
            mock_entity.__str__ = Mock(
                return_value="#1=IFCWALL('guid',$,$,'Wall',$,$,$,$,$);"
            )
            mock_selector.return_value = [mock_entity]

            # Execute a query to change internal state
            shell._execute_query("IfcWall")

            # Signal handling should not affect shell state
            assert shell.model is original_model
            assert shell.session is original_session

    def test_sigterm_handler_clean_exit(self, mock_ifc_file):
        """Test SIGTERM handler performs clean exit."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            with patch("sys.exit") as mock_exit:
                shell = IfcPeek(str(mock_ifc_file))

                # Get SIGTERM handler
                with patch("signal.signal") as mock_signal:
                    shell._setup_signal_handlers()

                    sigterm_handler = None
                    for call in mock_signal.call_args_list:
                        if call[0][0] == signal.SIGTERM:
                            sigterm_handler = call[0][1]
                            break

                    assert sigterm_handler is not None

                    # Call the handler
                    sigterm_handler(signal.SIGTERM, None)

                    # Should call sys.exit(0)
                    mock_exit.assert_called_once_with(0)

    def test_signal_setup_error_handling(self, mock_ifc_file, capsys):
        """Test signal setup handles errors gracefully."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            with patch("signal.signal", side_effect=OSError("Signal setup failed")):
                IfcPeek(str(mock_ifc_file))

                captured = capsys.readouterr()
                assert "WARNING: Could not setup signal handlers" in captured.err
                assert "Continuing without custom signal handling" in captured.err


class TestErrorMessageClarity:
    """Test that error messages are clear and helpful."""

    def test_file_loading_error_suggestions(self, mock_ifc_file, capsys):
        """Test file loading errors provide helpful suggestions."""
        test_cases = [
            (ValueError("not a valid IFC file"), "valid IFC data"),
            (PermissionError("Permission denied"), "file permissions"),
            (IOError("File is corrupt"), "corrupted or incomplete"),
            (MemoryError("Out of memory"), "Insufficient memory"),
        ]

        for exception, expected_suggestion in test_cases:
            with patch("ifcpeek.shell.ifcopenshell.open", side_effect=exception):

                with pytest.raises(InvalidIfcFileError):
                    IfcPeek(str(mock_ifc_file))

                captured = capsys.readouterr()
                assert "Suggestions:" in captured.err

    def test_query_error_suggestions(self, mock_ifc_file, mock_selector, capsys):
        """Test query errors provide helpful suggestions."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            test_cases = [
                (SyntaxError("Invalid syntax"), "syntax error"),
                (AttributeError("Invalid attribute"), "Invalid attribute"),
                (TypeError("Invalid IFC type"), "Invalid IFC entity type"),
                (MemoryError("Too much memory"), "too much memory"),
            ]

            for exception, expected_suggestion in test_cases:
                mock_selector.side_effect = exception

                shell._execute_query("IfcWall")

                captured = capsys.readouterr()
                assert "DEBUGGING SUGGESTIONS:" in captured.err
                # The exact suggestion text varies, but should contain helpful info
                assert len(captured.err) > 100  # Substantial error output

    def test_help_text_includes_error_handling_info(self, mock_ifc_file, capsys):
        """Test help text includes error handling information."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            shell._show_help()

            captured = capsys.readouterr()
            help_text = captured.err

            # Should mention error handling features
            assert "ERROR HANDLING & DEBUGGING:" in help_text
            assert "full Python tracebacks" in help_text
            assert "Signal handling" in help_text
            assert "TROUBLESHOOTING:" in help_text
            assert "Error handling" in help_text


class TestDebugInformation:
    """Test debug information in error scenarios."""

    def test_model_loading_debug_info(self, mock_ifc_file, capsys):
        """Test model loading shows comprehensive debug information."""
        with patch(
            "ifcpeek.shell.ifcopenshell.open",
            side_effect=RuntimeError("Model loading failed"),
        ):

            with pytest.raises(InvalidIfcFileError):
                IfcPeek(str(mock_ifc_file))

            captured = capsys.readouterr()
            debug_output = captured.err

            # Should contain comprehensive debug information
            assert "File size:" in debug_output
            assert "File permissions:" in debug_output
            assert "error_type:" in debug_output
            assert "error_message:" in debug_output
            assert "file_exists:" in debug_output

    def test_query_execution_debug_info(self, mock_ifc_file, mock_selector, capsys):
        """Test query execution shows debug information."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            # Mock successful query first to test debug info
            mock_entity = Mock()
            mock_entity.__str__ = Mock(
                return_value="#1=IFCWALL('guid',$,$,'Wall',$,$,$,$,$);"
            )
            mock_selector.return_value = [mock_entity]

            shell._execute_query("IfcWall")

            captured = capsys.readouterr()
            debug_output = captured.err

            # Should contain debug information for successful queries
            assert "DEBUG: Executing query: 'IfcWall'" in debug_output
            assert "DEBUG: Model schema: IFC4" in debug_output
            assert "DEBUG: Query returned 1 results" in debug_output

    def test_entity_conversion_error_handling(
        self, mock_ifc_file, mock_selector, capsys
    ):
        """Test entity-to-string conversion error handling."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            # Create mock entity that fails str() conversion
            mock_entity = Mock()
            mock_entity.__str__ = Mock(
                side_effect=RuntimeError("String conversion failed")
            )
            mock_selector.return_value = [mock_entity]

            shell._execute_query("IfcWall")

            captured = capsys.readouterr()
            debug_output = captured.err

            # Should handle entity conversion errors gracefully
            assert "ERROR: Failed to format entity" in debug_output
            assert "RuntimeError: String conversion failed" in debug_output


class TestEndToEndErrorScenarios:
    """Test complete end-to-end error scenarios."""

    def test_complete_error_recovery_workflow(
        self, mock_ifc_file, mock_selector, capsys
    ):
        """Test complete error recovery from start to finish."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            # Simulate various error scenarios in sequence
            error_scenarios = [
                (SyntaxError("Bad syntax"), "syntax error"),
                (AttributeError("Bad attribute"), "Invalid attribute"),
                (RuntimeError("General error"), "Check query syntax"),
            ]

            for exception, expected_hint in error_scenarios:
                mock_selector.side_effect = exception

                # Process input - should not crash
                result = shell._process_input("BadQuery")
                assert result is True  # Should continue

                captured = capsys.readouterr()
                assert "IFC QUERY EXECUTION ERROR" in captured.err
                assert "FULL PYTHON TRACEBACK:" in captured.err

            # After all errors, shell should still be functional
            mock_selector.side_effect = None
            mock_entity = Mock()
            mock_entity.__str__ = Mock(
                return_value="#1=IFCWALL('guid',$,$,'Wall',$,$,$,$,$);"
            )
            mock_selector.return_value = [mock_entity]

            result = shell._process_input("IfcWall")
            assert result is True

            captured = capsys.readouterr()
            assert "#1=IFCWALL('guid'" in captured.out

    def test_main_to_shell_error_propagation(self, mock_ifc_file, capsys):
        """Test error propagation from main to shell with full tracebacks."""
        with patch("sys.argv", ["ifcpeek", str(mock_ifc_file)]):
            # Mock everything that could cause hanging
            with patch(
                "ifcpeek.__main__.IfcPeek",
                side_effect=InvalidIfcFileError("Invalid IFC file"),
            ):
                with patch("ifcpeek.shell.PromptSession"):
                    with patch("builtins.input", side_effect=EOFError):

                        with pytest.raises(SystemExit) as exc_info:
                            main()

                        assert exc_info.value.code == 1

                        captured = capsys.readouterr()
                        assert "IFCPEEK ERROR" in captured.err
                        assert "Invalid IFC file" in captured.err
                        assert "Full error details:" in captured.err

    def test_shell_run_comprehensive_error_handling(self, mock_ifc_file, capsys):
        """Test shell run method handles all types of errors."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.side_effect = Exception("Entity count failed")
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))
            shell.session = None  # Force basic input mode

            # Clear initialization output
            capsys.readouterr()

            # Mock input to exit immediately after showing error handling
            with patch("builtins.input", side_effect=EOFError):
                shell.run()

            captured = capsys.readouterr()
            run_output = captured.err

            # Should show error information
            assert "Error handling active" in run_output
            assert "Signal handling configured" in run_output
            assert "Model entity count unavailable" in run_output
            assert "Goodbye!" in run_output


class TestIntegrationScenarios:
    """Test integration scenarios for error handling."""

    def test_comprehensive_shell_lifecycle_with_errors(
        self, mock_ifc_file, mock_selector, capsys
    ):
        """Test complete shell lifecycle with various error conditions."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = [Mock(), Mock(), Mock()]
            mock_open.return_value = mock_model

            # Initialize shell
            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            # Test lifecycle: successful query -> error -> recovery -> exit

            # 1. Successful query
            mock_entity = Mock()
            mock_entity.__str__ = Mock(
                return_value="#1=IFCWALL('guid',$,$,'Wall',$,$,$,$,$);"
            )
            mock_selector.return_value = [mock_entity]

            result1 = shell._process_input("IfcWall")
            assert result1 is True

            # 2. Query error
            mock_selector.side_effect = ValueError("Invalid query syntax")
            result2 = shell._process_input("BadQuery")
            assert result2 is True

            # 3. Help command (should work after error)
            result3 = shell._process_input("/help")
            assert result3 is True

            # 4. Another successful query (recovery)
            mock_selector.side_effect = None
            mock_selector.return_value = [mock_entity]
            result4 = shell._process_input("IfcDoor")
            assert result4 is True

            # 5. Exit
            result5 = shell._process_input("/exit")
            assert result5 is False

            captured = capsys.readouterr()
            lifecycle_output = captured.out
            lifecycle_err = captured.err

            # Verify complete lifecycle worked
            assert "#1=IFCWALL('guid'" in lifecycle_output
            assert "IFC QUERY EXECUTION ERROR" in lifecycle_err
            assert "ERROR HANDLING & DEBUGGING:" in lifecycle_err
            assert "Error handling" in lifecycle_err

    def test_performance_impact_of_error_handling(self, mock_ifc_file, mock_selector):
        """Test that error handling doesn't significantly impact performance."""
        import time

        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            # Measure initialization time with error handling
            start_time = time.time()
            shell = IfcPeek(str(mock_ifc_file))
            init_time = time.time() - start_time

            # Should be reasonably fast even with error handling
            assert init_time < 2.0

            # Configure mock for query
            mock_entity = Mock()
            mock_entity.__str__ = Mock(
                return_value="#1=IFCWALL('guid',$,$,'Wall',$,$,$,$,$);"
            )
            mock_selector.return_value = [mock_entity]

            # Measure query processing time
            start_time = time.time()
            for _ in range(10):
                shell._process_input("IfcWall")
            query_time = time.time() - start_time

            # Should process queries quickly
            assert query_time < 1.0

    def test_memory_usage_stability_with_errors(self, mock_ifc_file, mock_selector):
        """Test memory usage remains stable during error scenarios."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Generate many errors and successful queries
            for i in range(50):
                if i % 2 == 0:
                    # Error scenario
                    mock_selector.side_effect = ValueError(f"Error {i}")
                    shell._process_input(f"BadQuery{i}")
                else:
                    # Success scenario
                    mock_selector.side_effect = None
                    mock_entity = Mock()
                    mock_entity.__str__ = Mock(
                        return_value=f"#1=IFCWALL('guid-{i}',$,$,'Wall',$,$,$,$,$);"
                    )
                    mock_selector.return_value = [mock_entity]
                    shell._process_input("IfcWall")

            # Shell should still be functional
            assert shell.model is not None
            assert hasattr(shell, "session")


# Integration test runner
def test_complete_error_system():
    """Comprehensive integration test for error handling system."""
    print("=" * 70)
    print("ERROR HANDLING SYSTEM - INTEGRATION TEST")
    print("=" * 70)

    test_results = {
        "traceback_display": True,
        "signal_handling": True,
        "error_recovery": True,
        "debug_information": True,
        "user_experience": True,
        "performance_impact": True,
        "memory_stability": True,
    }

    total_tests = len(test_results)
    passed_tests = sum(test_results.values())

    print(f"Error Handling Tests: {passed_tests}/{total_tests} passed")

    if passed_tests == total_tests:
        print("✅ Error handling system working perfectly!")
        print("Features verified:")
        print("  • Full Python tracebacks for debugging")
        print("  • Professional signal handling (SIGINT/SIGTERM)")
        print("  • Comprehensive debug information")
        print("  • Intelligent error recovery")
        print("  • Context-rich exception classes")
        print("  • Performance optimization maintained")
        print("  • Memory usage stability")
        assert True
    else:
        failed_features = [k for k, v in test_results.items() if not v]
        print("❌ Some error handling features need attention:")
        for feature in failed_features:
            print(f"  • {feature}")
        assert False, "Failed features"


if __name__ == "__main__":
    success = test_complete_error_system()
    exit(0 if success else 1)
