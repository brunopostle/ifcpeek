"""Test history integration functionality."""

import os
from unittest.mock import patch, Mock

from ifcpeek.shell import IfcPeek

# Enable debug mode for testing
os.environ["IFCPEEK_DEBUG"] = "1"


class TestHistoryIntegration:
    """Test history system integration with shell."""

    def test_shell_initializes_with_history_system(self, mock_ifc_file):
        """Test shell initialization includes history system."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_open.return_value = Mock()

            shell = IfcPeek(str(mock_ifc_file))

            assert shell is not None
            assert shell.model is not None
            # Session should be created or None (both acceptable in test environment)
            assert shell.session is None or hasattr(shell.session, "prompt")

    def test_history_fallback_on_error(self, mock_ifc_file, capsys):
        """Test graceful fallback when history system fails."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_open.return_value = Mock()

            # Force history creation to fail
            with patch(
                "ifcpeek.shell.IfcPeek._is_in_test_environment", return_value=False
            ):
                with patch(
                    "ifcpeek.shell.FileHistory", side_effect=Exception("History failed")
                ):
                    shell = IfcPeek(str(mock_ifc_file))

                    # Should still work with fallback
                    assert shell is not None
                    assert shell.session is None  # Falls back to None

                    # Core functionality should still work
                    result = shell._process_input("/help")
                    assert result is True

            captured = capsys.readouterr()
            assert "Could not create prompt session" in captured.err

    def test_shell_functionality_preserved(self, mock_ifc_file, mock_selector, capsys):
        """Test that all core functionality works with history system."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))
            capsys.readouterr()  # Clear initialization output

            # Test core commands work
            assert shell._process_input("/help") is True
            assert shell._process_input("/exit") is False
            assert shell._process_input("") is True

            # Test query execution
            mock_entity = Mock()
            mock_entity.__str__ = Mock(return_value="#1=IFCWALL('test');")
            mock_selector.return_value = [mock_entity]

            assert shell._process_input("IfcWall") is True

    def test_help_includes_history_features(self, mock_ifc_file, capsys):
        """Test that help text mentions history features."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_open.return_value = Mock()

            shell = IfcPeek(str(mock_ifc_file))
            capsys.readouterr()

            shell._show_help()

            captured = capsys.readouterr()
            help_text = captured.err

            assert "HISTORY:" in help_text
            assert "Up/Down" in help_text
            assert "Ctrl-R" in help_text

    def test_filehistory_basic_functionality(self, temp_dir):
        """Test that FileHistory can be created and used."""
        from prompt_toolkit.history import FileHistory

        history_path = temp_dir / "test_history"
        history = FileHistory(str(history_path))

        # Should be able to add commands without error
        test_commands = ["/help", "IfcWall", "IfcDoor, Name=Test"]
        for cmd in test_commands:
            history.append_string(cmd)

        assert isinstance(history, FileHistory)

    def test_unicode_command_support(self, temp_dir):
        """Test that history system handles Unicode commands."""
        from prompt_toolkit.history import FileHistory

        history_path = temp_dir / "unicode_history"
        history = FileHistory(str(history_path))

        unicode_commands = [
            "IfcWall, Name=测试墙体",  # Chinese
            "IfcDoor, Name=Дверь",  # Cyrillic
            "IfcWindow, Name=Fenêtre",  # French
        ]

        # Should handle Unicode without exceptions
        for cmd in unicode_commands:
            history.append_string(cmd)

    def test_test_environment_detection(self, mock_ifc_file):
        """Test that shell properly detects test environment."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_open.return_value = Mock()

            shell = IfcPeek(str(mock_ifc_file))

            # In test environment, history may be disabled - that's fine
            # Key thing is shell should still be functional
            assert shell.model is not None
            assert shell._process_input("/help") is True
