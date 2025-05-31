"""Streamlined tests for configuration management."""

import os
import stat
from pathlib import Path
from unittest.mock import patch
import pytest

from ifcpeek.config import (
    get_config_dir,
    get_history_file_path,
    validate_ifc_file_path,
)
from ifcpeek.exceptions import (
    ConfigurationError,
    FileNotFoundError,
    InvalidIfcFileError,
)


class TestConfigDirectory:
    """Test configuration directory management."""

    def test_get_config_dir_with_xdg_state_home(self):
        """Test config directory with XDG_STATE_HOME set."""
        test_xdg_path = "/custom/xdg/state"

        with patch.dict(os.environ, {"XDG_STATE_HOME": test_xdg_path}):
            config_dir = get_config_dir()

        expected = Path(test_xdg_path) / "ifcpeek"
        assert config_dir == expected

    def test_get_config_dir_without_xdg_state_home(self):
        """Test config directory without XDG_STATE_HOME."""
        env = os.environ.copy()
        env.pop("XDG_STATE_HOME", None)

        with patch.dict(os.environ, env, clear=True):
            with patch("pathlib.Path.home") as mock_home:
                mock_home.return_value = Path("/home/user")
                config_dir = get_config_dir()

        expected = Path("/home/user") / ".local" / "state" / "ifcpeek"
        assert config_dir == expected


class TestHistoryFilePath:
    """Test history file path management."""

    def test_get_history_file_path_creates_directory(self, temp_dir):
        """Test that history file path creates necessary directories."""
        config_path = temp_dir / "config"

        with patch("ifcpeek.config.get_config_dir", return_value=config_path):
            history_path = get_history_file_path()

        assert config_path.exists()
        assert config_path.is_dir()
        assert history_path == config_path / "history"

    def test_get_history_file_path_permission_error(self, temp_dir):
        """Test history file path with permission errors."""
        readonly_dir = temp_dir / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)  # r-x------

        config_path = readonly_dir / "ifcpeek"

        with patch("ifcpeek.config.get_config_dir", return_value=config_path):
            try:
                with pytest.raises(
                    ConfigurationError,
                    match="Failed to create history file path.*Permission denied",
                ):
                    get_history_file_path()
            finally:
                readonly_dir.chmod(stat.S_IRWXU)  # Restore for cleanup


class TestFileValidation:
    """Test IFC file validation."""

    def test_validate_existing_ifc_file(self, temp_dir):
        """Test validation of existing IFC file."""
        ifc_file = temp_dir / "test.ifc"
        ifc_file.write_text("ISO-10303-21;")

        result = validate_ifc_file_path(str(ifc_file))
        assert result == ifc_file
        assert isinstance(result, Path)

    def test_validate_nonexistent_file(self, temp_dir):
        """Test validation of non-existent file."""
        nonexistent = temp_dir / "missing.ifc"

        with pytest.raises(FileNotFoundError, match="File .* not found"):
            validate_ifc_file_path(str(nonexistent))

    def test_validate_directory_instead_of_file(self, temp_dir):
        """Test validation when path points to directory."""
        directory = temp_dir / "test.ifc"
        directory.mkdir()

        with pytest.raises(InvalidIfcFileError, match=".* is not a file"):
            validate_ifc_file_path(str(directory))

    def test_validate_wrong_extension(self, temp_dir):
        """Test validation of file with wrong extension."""
        txt_file = temp_dir / "test.txt"
        txt_file.write_text("Not an IFC file")

        with pytest.raises(
            InvalidIfcFileError, match="does not appear to be an IFC file"
        ):
            validate_ifc_file_path(str(txt_file))

    def test_validate_case_insensitive_extension(self, temp_dir):
        """Test validation accepts case-insensitive IFC extensions."""
        extensions = [".ifc", ".IFC", ".Ifc", ".IfC"]

        for ext in extensions:
            ifc_file = temp_dir / f"test{ext}"
            ifc_file.write_text("ISO-10303-21;")

            result = validate_ifc_file_path(str(ifc_file))
            assert result == ifc_file

            ifc_file.unlink()

    def test_validate_ifc_content_with_unusual_extension(self, temp_dir):
        """Test validation of IFC content with unusual extension."""
        ifc_file = temp_dir / "test.model"
        ifc_file.write_text(
            "ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;"
        )

        result = validate_ifc_file_path(str(ifc_file))
        assert result == ifc_file


class TestDebugMode:
    """Test debug mode functionality."""

    def test_debug_output_in_validation(self, temp_dir, capsys):
        """Test that validation produces debug output when enabled."""
        original_debug = os.environ.get("IFCPEEK_DEBUG")
        os.environ["IFCPEEK_DEBUG"] = "1"

        try:
            ifc_file = temp_dir / "debug_test.ifc"
            ifc_file.write_text("ISO-10303-21;")

            validate_ifc_file_path(str(ifc_file))

            captured = capsys.readouterr()
            debug_output = captured.err

            assert "DEBUG: Validating IFC file path:" in debug_output
            assert "DEBUG: File size:" in debug_output
            assert "DEBUG: File validation successful:" in debug_output
        finally:
            if original_debug is None:
                os.environ.pop("IFCPEEK_DEBUG", None)
            else:
                os.environ["IFCPEEK_DEBUG"] = original_debug

    def test_debug_mode_disabled_by_default(self, temp_dir, capsys):
        """Test that debug output is disabled by default."""
        original_debug = os.environ.get("IFCPEEK_DEBUG")
        os.environ.pop("IFCPEEK_DEBUG", None)

        try:
            ifc_file = temp_dir / "no_debug_test.ifc"
            ifc_file.write_text("ISO-10303-21;")

            validate_ifc_file_path(str(ifc_file))

            captured = capsys.readouterr()
            debug_output = captured.err

            assert "DEBUG: Validating IFC file path:" not in debug_output
        finally:
            if original_debug is not None:
                os.environ["IFCPEEK_DEBUG"] = original_debug


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_unicode_paths(self, temp_dir):
        """Test handling of Unicode characters in paths."""
        unicode_file = temp_dir / "测试文件.ifc"  # Chinese characters
        unicode_file.write_text("ISO-10303-21;")

        result = validate_ifc_file_path(str(unicode_file))
        assert result == unicode_file

    def test_spaces_in_paths(self, temp_dir):
        """Test handling of spaces in file paths."""
        spaced_file = temp_dir / "file with spaces.ifc"
        spaced_file.write_text("ISO-10303-21;")

        result = validate_ifc_file_path(str(spaced_file))
        assert result == spaced_file

    def test_none_filename(self):
        """Test handling of None filename."""
        with pytest.raises(TypeError, match="expected str, bytes or os.PathLike"):
            validate_ifc_file_path(None)

    def test_current_directory_path(self):
        """Test handling of current directory path."""
        with pytest.raises(InvalidIfcFileError, match="is not a file"):
            validate_ifc_file_path(".")


# Test fixtures
@pytest.fixture
def temp_dir(tmp_path):
    """Provide a temporary directory for tests."""
    return tmp_path
