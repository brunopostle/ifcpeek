"""
test_error_handling.py - Essential error handling tests
"""

import pytest
import signal
import os
from unittest.mock import patch, Mock

from ifcpeek.shell import IfcPeek
from ifcpeek.__main__ import main
from ifcpeek.exceptions import FileNotFoundError, InvalidIfcFileError

os.environ["IFCPEEK_DEBUG"] = "1"


class TestCoreErrorHandling:
    """Essential error handling tests."""

    def test_query_error_shows_traceback(self, mock_ifc_file, capsys):
        """Test query errors show full traceback."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))
            capsys.readouterr()  # Clear

            with patch(
                "ifcpeek.shell.ifcopenshell.util.selector.filter_elements",
                side_effect=ValueError("Test error"),
            ):
                shell._execute_query("BadQuery")

                captured = capsys.readouterr()
                assert "IFC QUERY EXECUTION ERROR" in captured.err
                assert "FULL PYTHON TRACEBACK:" in captured.err
                assert "ValueError" in captured.err
                assert "Test error" in captured.err

    def test_file_loading_error_debug(self, mock_ifc_file, capsys):
        """Test file loading errors show debug info."""
        with patch(
            "ifcpeek.shell.ifcopenshell.open", side_effect=RuntimeError("Parse failed")
        ):

            with pytest.raises(InvalidIfcFileError):
                IfcPeek(str(mock_ifc_file))

            captured = capsys.readouterr()
            assert "IFC MODEL LOADING ERROR" in captured.err
            assert "file_path:" in captured.err
            assert "file_size:" in captured.err

    def test_signal_handlers_setup(self, mock_ifc_file):
        """Test signal handlers are configured."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            with patch("signal.signal") as mock_signal:
                IfcPeek(str(mock_ifc_file))

                # Verify SIGINT and SIGTERM handlers set
                calls = mock_signal.call_args_list
                signal_nums = [call[0][0] for call in calls]
                assert signal.SIGINT in signal_nums
                assert signal.SIGTERM in signal_nums

    def test_sigint_handler_message(self, mock_ifc_file, capsys):
        """Test SIGINT handler shows helpful message."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))
            capsys.readouterr()  # Clear

            # Get and test SIGINT handler
            with patch("signal.signal") as mock_signal:
                shell._setup_signal_handlers()

                sigint_handler = None
                for call in mock_signal.call_args_list:
                    if call[0][0] == signal.SIGINT:
                        sigint_handler = call[0][1]
                        break

                assert sigint_handler is not None
                sigint_handler(signal.SIGINT, None)

                captured = capsys.readouterr()
                assert "(Use Ctrl-D to exit" in captured.err

    def test_error_recovery(self, mock_ifc_file, capsys):
        """Test shell continues after errors."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))
            capsys.readouterr()  # Clear

            # Simulate error in _execute_query
            def failing_execute(query):
                raise RuntimeError("Query failed")

            shell._execute_query = failing_execute

            # Should not crash
            result = shell._process_input("BadQuery")
            assert result is True

            captured = capsys.readouterr()
            assert "ERROR: Unexpected error processing input" in captured.err
            assert "Shell will continue" in captured.err

    def test_main_error_handling(self, mock_ifc_file, capsys):
        """Test main function error handling."""
        with patch("sys.argv", ["ifcpeek", str(mock_ifc_file)]):
            with patch(
                "ifcpeek.__main__.IfcPeek", side_effect=RuntimeError("Startup failed")
            ):

                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 1

                captured = capsys.readouterr()
                assert "UNEXPECTED ERROR" in captured.err
                assert "Startup failed" in captured.err


class TestExceptionClasses:
    """Test custom exception classes."""

    def test_file_not_found_error_context(self):
        """Test FileNotFoundError includes context."""
        error = FileNotFoundError("File missing", file_path="/path/to/file.ifc")
        assert "file_path=/path/to/file.ifc" in str(error)

    def test_invalid_ifc_file_error_context(self):
        """Test InvalidIfcFileError includes context."""
        error = InvalidIfcFileError(
            "Invalid file",
            file_path="/path/to/file.ifc",
            file_size=1024,
            error_type="ParseError",
        )
        error_str = str(error)
        assert "file_path=/path/to/file.ifc" in error_str
        assert "file_size=1024" in error_str
        assert "error_type=ParseError" in error_str


class TestDebugOutput:
    """Test debug output functionality."""

    def test_successful_query_debug_info(self, mock_ifc_file, mock_selector, capsys):
        """Test successful queries show debug info."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))
            capsys.readouterr()  # Clear

            mock_entity = Mock()
            mock_entity.__str__ = Mock(
                return_value="#1=IFCWALL('guid',$,$,'Wall',$,$,$,$,$);"
            )
            mock_selector.return_value = [mock_entity]

            shell._execute_query("IfcWall")

            captured = capsys.readouterr()
            assert "DEBUG: Executing query: 'IfcWall'" in captured.err
            assert "DEBUG: Model schema: IFC4" in captured.err
            assert "DEBUG: Query returned 1 results" in captured.err

    def test_entity_conversion_error(self, mock_ifc_file, mock_selector, capsys):
        """Test entity string conversion error handling."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))
            capsys.readouterr()  # Clear

            mock_entity = Mock()
            mock_entity.__str__ = Mock(side_effect=RuntimeError("Conversion failed"))
            mock_selector.return_value = [mock_entity]

            shell._execute_query("IfcWall")

            captured = capsys.readouterr()
            assert "ERROR: Failed to format entity" in captured.err
            assert "RuntimeError: Conversion failed" in captured.err


# Run tests
if __name__ == "__main__":
    # This allows the file to be run directly for debugging
    import pytest

    pytest.main([__file__])
