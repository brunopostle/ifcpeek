"""Streamlined test shell module functionality."""

import pytest
from unittest.mock import patch, Mock

from ifcpeek.shell import IfcPeek
from ifcpeek.exceptions import FileNotFoundError, InvalidIfcFileError


class TestIfcPeekInitialization:
    """Test IfcPeek class initialization with IFC loading."""

    def test_init_loads_ifc_model_successfully(self, mock_ifc_file):
        """Test IfcPeek initialization loads IFC model successfully."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = ["entity1", "entity2", "entity3"]
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            assert shell.model == mock_model
            assert hasattr(shell, "session")
            mock_open.assert_called_once_with(str(mock_ifc_file))

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


class TestQueryExecution:
    """Test IFC query execution functionality."""

    def test_process_input_executes_queries(self, mock_ifc_file, mock_selector, capsys):
        """Test that _process_input executes IFC queries."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))
            capsys.readouterr()  # Clear initialization output

            mock_entity = Mock()
            mock_entity.__str__ = Mock(
                return_value="#1=IFCWALL('test-guid',$,$,'TestWall',$,$,$,$,$);"
            )
            mock_selector.return_value = [mock_entity]

            result = shell._process_input("IfcWall")

            assert result is True
            captured = capsys.readouterr()
            assert "#1=IFCWALL('test-guid'" in captured.out
            mock_selector.assert_called_once_with(mock_model, "IfcWall")

    def test_process_input_handles_invalid_queries(
        self, mock_ifc_file, mock_selector, capsys
    ):
        """Test that _process_input handles invalid IFC queries with error messages."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))
            capsys.readouterr()

            mock_selector.side_effect = Exception("Invalid selector syntax")
            result = shell._process_input("invalid query")

            assert result is True
            captured = capsys.readouterr()
            assert "IFC QUERY EXECUTION ERROR" in captured.err

    def test_process_input_handles_empty_input(self, mock_ifc_file, mock_selector):
        """Test that _process_input handles empty input correctly."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))
            result = shell._process_input("")

            assert result is True
            mock_selector.assert_not_called()


class TestBuiltinCommands:
    """Test built-in command functionality."""

    def test_help_command(self, mock_ifc_file, capsys):
        """Test that /help command displays help text."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))
            capsys.readouterr()

            result = shell._process_input("/help")

            assert result is True
            captured = capsys.readouterr()
            assert "IfcPeek - Interactive IFC Model Query Tool" in captured.err

    def test_exit_commands(self, mock_ifc_file):
        """Test that /exit and /quit commands return False."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            assert shell._process_input("/exit") is False
            assert shell._process_input("/quit") is False


class TestShellRunMethod:
    """Test the shell run method."""

    def test_run_handles_eof_gracefully(self, mock_ifc_file, capsys):
        """Test run method handles EOFError (Ctrl-D) gracefully."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))
            capsys.readouterr()

            with patch.object(shell, "session") as mock_session:
                mock_session.prompt.side_effect = EOFError
                shell.run()

            captured = capsys.readouterr()
            assert "Goodbye!" in captured.err

    def test_run_handles_keyboard_interrupt(self, mock_ifc_file, capsys):
        """Test run method handles KeyboardInterrupt (Ctrl-C) gracefully."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))
            capsys.readouterr()

            with patch.object(shell, "session") as mock_session:
                mock_session.prompt.side_effect = [KeyboardInterrupt, EOFError]
                shell.run()

            captured = capsys.readouterr()
            assert "(Use Ctrl-D to exit)" in captured.err
            assert "Goodbye!" in captured.err
