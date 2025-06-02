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

            shell = IfcPeek(str(mock_ifc_file), force_interactive=True)

            assert shell is not None
            assert shell.model is not None
            # Session should be created or None (both acceptable in test environment)
            assert shell.session is None or hasattr(shell.session, "prompt")

    def test_history_fallback_on_error(self, mock_ifc_file, capsys):
        """Test graceful fallback when history system fails."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_open.return_value = Mock()

            # Force history creation to fail by making FileHistory raise an exception
            with patch(
                "ifcpeek.shell.FileHistory", side_effect=Exception("History failed")
            ):
                shell = IfcPeek(str(mock_ifc_file), force_interactive=True)

                # Should still work with fallback
                assert shell is not None
                assert shell.session is None  # Falls back to None

                # Core functionality should still work
                result = shell._process_input("/help")
                assert result is True

            captured = capsys.readouterr()
            assert "Could not create session with history" in captured.err

    def test_history_fallback_on_session_creation_error(self, mock_ifc_file, capsys):
        """Test graceful fallback when entire session creation fails."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_open.return_value = Mock()

            # Force session creation to fail completely
            with patch(
                "ifcpeek.shell.PromptSession", side_effect=Exception("Session failed")
            ):
                shell = IfcPeek(str(mock_ifc_file), force_interactive=True)

                # Should still work with fallback
                assert shell is not None
                assert shell.session is None  # Falls back to None

                # Core functionality should still work
                result = shell._process_input("/help")
                assert result is True

            captured = capsys.readouterr()
            assert "Could not create session with history" in captured.err

    def test_shell_functionality_preserved(self, mock_ifc_file, mock_selector, capsys):
        """Test that all core functionality works with history system."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file), force_interactive=True)
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

            shell = IfcPeek(str(mock_ifc_file), force_interactive=True)
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

    def test_shell_works_without_history(self, mock_ifc_file, mock_selector):
        """Test that shell works correctly when history is disabled."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_open.return_value = mock_model

            # Force both history file creation and session creation to fail
            with patch(
                "ifcpeek.config.get_history_file_path",
                side_effect=Exception("No history"),
            ):
                with patch(
                    "ifcpeek.shell.FileHistory", side_effect=Exception("No FileHistory")
                ):
                    shell = IfcPeek(str(mock_ifc_file), force_interactive=True)

                    # Shell should still be functional
                    assert shell.model is not None
                    assert shell.session is None  # No session created
                    assert shell._process_input("/help") is True

                    # Queries should still work
                    mock_entity = Mock()
                    mock_entity.__str__ = Mock(return_value="#1=IFCWALL('test');")
                    mock_selector.return_value = [mock_entity]

                    assert shell._process_input("IfcWall") is True

    def test_completion_system_works_with_history_failures(self, mock_ifc_file):
        """Test that completion system still works when history fails."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            # Create a proper mock model that supports iteration
            mock_model = Mock()

            # Mock entities for iteration
            mock_entity = Mock()
            mock_entity.is_a.return_value = "IfcWall"
            mock_model.__iter__ = Mock(return_value=iter([mock_entity]))

            # Mock by_type for property sets
            mock_model.by_type.return_value = []

            # Mock schema properly
            mock_schema_class = Mock()
            mock_schema_class.attributes.return_value = []
            mock_schema_class.inverse_attributes.return_value = []
            mock_schema_class.supertypes.return_value = []

            mock_schema = Mock()
            mock_schema.declaration_by_name.return_value = mock_schema_class
            mock_model.schema = mock_schema

            mock_open.return_value = mock_model

            # Force history to fail but completion should still work
            with patch(
                "ifcpeek.shell.FileHistory", side_effect=Exception("History failed")
            ):
                shell = IfcPeek(str(mock_ifc_file), force_interactive=True)

                # Completion cache should still be built despite history failure
                assert shell.completion_cache is not None
                assert shell.completer is not None

                # Shell should work
                assert shell._process_input("/help") is True

    def test_shell_works_when_completion_cache_fails(self, mock_ifc_file, capsys):
        """Test that shell works even when completion cache building fails."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_open.return_value = mock_model

            # Clear any previous captured output from initialization
            capsys.readouterr()

            # The most reliable way to make the completion system fail is to patch
            # the create_dynamic_completion_system function itself
            original_create_fn = None
            try:
                # Import and patch the function
                import ifcpeek.dynamic_completion as dc_module

                original_create_fn = dc_module.create_dynamic_completion_system

                def failing_create_system(model):
                    raise Exception("Completion system creation failed")

                dc_module.create_dynamic_completion_system = failing_create_system

                # Now create the shell - this should trigger the completion cache failure
                shell = IfcPeek(str(mock_ifc_file), force_interactive=True)

                # Verify that completion cache failed to build
                assert shell.completion_cache is None
                assert shell.completer is None

                # But shell should still work for basic operations
                assert shell._process_input("/help") is True

                # Verify the error message was logged
                captured = capsys.readouterr()
                assert "Failed to build enhanced completion system" in captured.err

            finally:
                # Restore the original function
                if original_create_fn:
                    dc_module.create_dynamic_completion_system = original_create_fn

    def test_run_method_handles_no_session(self, mock_ifc_file, capsys):
        """Test that run method handles cases where session is None."""
        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_open.return_value = mock_model

            # Create shell with no session
            with patch(
                "ifcpeek.shell.PromptSession", side_effect=Exception("No session")
            ):
                shell = IfcPeek(str(mock_ifc_file), force_interactive=True)
                assert shell.session is None

                # Mock the input function to simulate user input
                with patch("builtins.input", side_effect=["IfcWall", EOFError]):
                    shell.run()

            captured = capsys.readouterr()
            assert "Goodbye!" in captured.err
