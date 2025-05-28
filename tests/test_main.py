"""Test main module functionality for Step 3."""

import subprocess
import sys
from unittest.mock import patch, MagicMock
import pytest

from ifcpeek.__main__ import main
from ifcpeek.exceptions import IfcPeekError, FileNotFoundError, InvalidIfcFileError


class TestArgumentParsing:
    """Test command-line argument parsing."""

    def test_main_requires_ifc_file_argument(self, capsys):
        """Test that main function requires IFC file argument."""
        with patch("sys.argv", ["ifcpeek"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

            # Should exit with error code 2 (argparse error)
            assert exc_info.value.code == 2

        captured = capsys.readouterr()
        assert "required" in captured.err.lower() or "arguments" in captured.err.lower()

    def test_main_with_valid_ifc_file_arg(self, mock_ifc_file, capsys):
        """Test main function with valid IFC file argument."""
        with patch("sys.argv", ["ifcpeek", str(mock_ifc_file)]):
            # Mock IfcPeek to avoid actual file operations
            with patch("ifcpeek.__main__.IfcPeek") as mock_shell_class:
                mock_shell_instance = MagicMock()
                mock_shell_class.return_value = mock_shell_instance

                main()

                # Verify IfcPeek was instantiated with correct path
                mock_shell_class.assert_called_once_with(str(mock_ifc_file))
                # Verify run method was called
                mock_shell_instance.run.assert_called_once()

    def test_main_with_invalid_file_path(self, capsys):
        """Test main function with invalid file path."""
        invalid_path = "/nonexistent/path/test.ifc"

        with patch("sys.argv", ["ifcpeek", invalid_path]):
            with pytest.raises(SystemExit) as exc_info:
                main()

            # Should exit with error code 1
            assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "Error:" in captured.err
        assert "not found" in captured.err

    def test_argument_parser_help(self, capsys):
        """Test argument parser help functionality."""
        for help_flag in ["-h", "--help"]:
            with patch("sys.argv", ["ifcpeek", help_flag]):
                with pytest.raises(SystemExit) as exc_info:
                    main()

                # Help should exit with code 0
                assert exc_info.value.code == 0

            captured = capsys.readouterr()
            assert "Interactive shell for querying IFC models" in captured.out
            assert "Path to IFC file" in captured.out


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

    def test_main_handles_generic_ifcpeek_error(self, capsys):
        """Test main function handles generic IfcPeekError."""
        with patch("sys.argv", ["ifcpeek", "test.ifc"]):
            with patch(
                "ifcpeek.__main__.IfcPeek", side_effect=IfcPeekError("Generic error")
            ):
                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "Error: Generic error" in captured.err

    def test_main_handles_keyboard_interrupt(self):
        """Test main function handles KeyboardInterrupt."""
        with patch("sys.argv", ["ifcpeek", "test.ifc"]):
            with patch("ifcpeek.__main__.IfcPeek", side_effect=KeyboardInterrupt):
                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 0

    def test_main_handles_unexpected_error(self, capsys):
        """Test main function handles unexpected errors."""
        with patch("sys.argv", ["ifcpeek", "test.ifc"]):
            with patch(
                "ifcpeek.__main__.IfcPeek",
                side_effect=RuntimeError("Unexpected error"),
            ):
                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "Unexpected error: Unexpected error" in captured.err


class TestShellIntegration:
    """Test integration between main and shell modules."""

    def test_main_imports_shell_correctly(self):
        """Test that main can import IfcPeek from shell module."""
        from ifcpeek.__main__ import main
        from ifcpeek.shell import IfcPeek

        # Should be able to import both without issues
        assert callable(main)
        assert callable(IfcPeek)

    def test_main_instantiates_shell_with_correct_path(self, mock_ifc_file):
        """Test that main instantiates IfcPeek with correct file path."""
        with patch("sys.argv", ["ifcpeek", str(mock_ifc_file)]):
            with patch("ifcpeek.__main__.IfcPeek") as mock_shell_class:
                mock_shell_instance = MagicMock()
                mock_shell_class.return_value = mock_shell_instance

                main()

                # Verify correct instantiation
                mock_shell_class.assert_called_once_with(str(mock_ifc_file))
                mock_shell_instance.run.assert_called_once()

    def test_main_propagates_shell_exceptions(self):
        """Test that exceptions from shell propagate correctly to main."""
        test_exceptions = [
            FileNotFoundError("File error"),
            InvalidIfcFileError("IFC error"),
            IfcPeekError("Shell error"),
        ]

        for exception in test_exceptions:
            with patch("sys.argv", ["ifcpeek", "test.ifc"]):
                with patch("ifcpeek.__main__.IfcPeek", side_effect=exception):
                    with pytest.raises(SystemExit) as exc_info:
                        main()

                    assert exc_info.value.code == 1


class TestConsoleScriptIntegration:
    """Test console script entry point."""

    def test_console_script_entry_point_exists(self):
        """Test that the console script entry point is properly configured."""
        # Test that the ifcpeek command can be found through module import
        result = subprocess.run(
            [sys.executable, "-c", 'import ifcpeek.__main__; print("OK")'],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "OK" in result.stdout

    def test_main_module_execution_shows_help(self):
        """Test that the module can be executed directly with help."""
        result = subprocess.run(
            [sys.executable, "-m", "ifcpeek", "--help"], capture_output=True, text=True
        )

        # Should show help and exit cleanly
        assert result.returncode == 0
        assert "Interactive shell for querying IFC models" in result.stdout
        assert "Path to IFC file" in result.stdout

    def test_main_module_execution_requires_file(self):
        """Test that module execution requires IFC file argument."""
        result = subprocess.run(
            [sys.executable, "-m", "ifcpeek"], capture_output=True, text=True
        )

        # Should exit with error code 2 (argparse error)
        assert result.returncode == 2
        assert (
            "required" in result.stderr.lower() or "arguments" in result.stderr.lower()
        )


class TestPathHandling:
    """Test various path handling scenarios."""

    def test_main_with_relative_path(self, temp_dir, capsys):
        """Test main function with relative path."""
        ifc_file = temp_dir / "test.ifc"
        ifc_file.write_text("ISO-10303-21;")

        # Change to temp directory
        import os
        from pathlib import Path

        original_cwd = Path.cwd()
        try:
            os.chdir(temp_dir)

            with patch("sys.argv", ["ifcpeek", "test.ifc"]):
                with patch("ifcpeek.__main__.IfcPeek") as mock_shell_class:
                    mock_shell_instance = MagicMock()
                    mock_shell_class.return_value = mock_shell_instance

                    main()

                    # Should work with relative path
                    mock_shell_class.assert_called_once_with("test.ifc")

        finally:
            os.chdir(original_cwd)

    def test_main_with_absolute_path(self, mock_ifc_file):
        """Test main function with absolute path."""
        absolute_path = str(mock_ifc_file.resolve())

        with patch("sys.argv", ["ifcpeek", absolute_path]):
            with patch("ifcpeek.__main__.IfcPeek") as mock_shell_class:
                mock_shell_instance = MagicMock()
                mock_shell_class.return_value = mock_shell_instance

                main()

                mock_shell_class.assert_called_once_with(absolute_path)

    def test_main_with_path_containing_spaces(self, temp_dir):
        """Test main function with path containing spaces."""
        ifc_file = temp_dir / "file with spaces.ifc"
        ifc_file.write_text("ISO-10303-21;")

        with patch("sys.argv", ["ifcpeek", str(ifc_file)]):
            with patch("ifcpeek.__main__.IfcPeek") as mock_shell_class:
                mock_shell_instance = MagicMock()
                mock_shell_class.return_value = mock_shell_instance

                main()

                mock_shell_class.assert_called_once_with(str(ifc_file))
