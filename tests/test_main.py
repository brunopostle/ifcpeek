"""Streamlined tests for main module functionality."""

import subprocess
import sys
from unittest.mock import patch, MagicMock
import pytest

from ifcpeek.__main__ import main
from ifcpeek.exceptions import FileNotFoundError, InvalidIfcFileError


class TestArgumentParsing:
    """Test command-line argument parsing."""

    def test_main_requires_ifc_file_argument(self, capsys):
        """Test that main function requires IFC file argument."""
        with patch("sys.argv", ["ifcpeek"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2

        captured = capsys.readouterr()
        assert "required" in captured.err.lower()

    def test_main_with_valid_ifc_file_arg(self, mock_ifc_file):
        """Test main function with valid IFC file argument."""
        with patch("sys.argv", ["ifcpeek", str(mock_ifc_file)]):
            with patch("ifcpeek.__main__.IfcPeek") as mock_shell_class:
                mock_shell_instance = MagicMock()
                mock_shell_class.return_value = mock_shell_instance

                main()

                mock_shell_class.assert_called_once_with(
                    str(mock_ifc_file), force_interactive=False
                )
                mock_shell_instance.run.assert_called_once()

    def test_argument_parser_help(self, capsys):
        """Test argument parser help functionality."""
        with patch("sys.argv", ["ifcpeek", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "Interactive shell for querying IFC models" in captured.out


class TestErrorHandling:
    """Test error handling in main function."""

    def test_main_handles_file_not_found_error(self, capsys):
        """Test main function handles FileNotFoundError."""
        with patch("sys.argv", ["ifcpeek", "missing.ifc"]):
            with patch(
                "ifcpeek.__main__.IfcPeek",
                side_effect=FileNotFoundError("File not found"),
            ):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "Error: File not found" in captured.err

    def test_main_handles_invalid_ifc_file_error(self, capsys):
        """Test main function handles InvalidIfcFileError."""
        with patch("sys.argv", ["ifcpeek", "invalid.txt"]):
            with patch(
                "ifcpeek.__main__.IfcPeek",
                side_effect=InvalidIfcFileError("Invalid IFC"),
            ):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "Error: Invalid IFC" in captured.err

    def test_main_handles_keyboard_interrupt(self):
        """Test main function handles KeyboardInterrupt."""
        with patch("sys.argv", ["ifcpeek", "test.ifc"]):
            with patch("ifcpeek.__main__.IfcPeek", side_effect=KeyboardInterrupt):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 0


class TestConsoleScriptIntegration:
    """Test console script entry point."""

    def test_main_module_execution_shows_help(self):
        """Test that the module can be executed directly with help."""
        result = subprocess.run(
            [sys.executable, "-m", "ifcpeek", "--help"], capture_output=True, text=True
        )

        assert result.returncode == 0
        assert "Interactive shell for querying IFC models" in result.stdout

    def test_main_module_execution_requires_file(self):
        """Test that module execution requires IFC file argument."""
        result = subprocess.run(
            [sys.executable, "-m", "ifcpeek"], capture_output=True, text=True
        )

        assert result.returncode == 2
        assert "required" in result.stderr.lower()
