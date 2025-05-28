"""Test configuration management functionality with fixed error handling expectations."""

import os
import stat
from pathlib import Path
from unittest.mock import patch, Mock
import pytest

from ifcpeek.config import (
    get_config_dir,
    get_history_file_path,
    get_cache_dir,
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
        # Remove XDG_STATE_HOME if it exists
        env = os.environ.copy()
        env.pop("XDG_STATE_HOME", None)

        with patch.dict(os.environ, env, clear=True):
            with patch("pathlib.Path.home") as mock_home:
                mock_home.return_value = Path("/home/user")
                config_dir = get_config_dir()

        expected = Path("/home/user") / ".local" / "state" / "ifcpeek"
        assert config_dir == expected

    def test_get_config_dir_handles_path_errors(self):
        """Test config directory creation handles path resolution errors."""
        with patch("pathlib.Path.home", side_effect=RuntimeError("Home error")):
            with pytest.raises(
                ConfigurationError, match="Failed to determine config directory"
            ):
                get_config_dir()

    def test_get_cache_dir_with_xdg_cache_home(self):
        """Test cache directory with XDG_CACHE_HOME set."""
        test_cache_path = "/custom/cache"

        with patch.dict(os.environ, {"XDG_CACHE_HOME": test_cache_path}):
            cache_dir = get_cache_dir()

        expected = Path(test_cache_path) / "ifcpeek"
        assert cache_dir == expected

    def test_get_cache_dir_without_xdg_cache_home(self):
        """Test cache directory without XDG_CACHE_HOME."""
        env = os.environ.copy()
        env.pop("XDG_CACHE_HOME", None)

        with patch.dict(os.environ, env, clear=True):
            with patch("pathlib.Path.home") as mock_home:
                mock_home.return_value = Path("/home/user")
                cache_dir = get_cache_dir()

        expected = Path("/home/user") / ".cache" / "ifcpeek"
        assert cache_dir == expected


class TestHistoryFilePath:
    """Test history file path management."""

    def test_get_history_file_path_creates_directory(self, temp_dir):
        """Test that history file path creates necessary directories."""
        config_path = temp_dir / "config"

        with patch("ifcpeek.config.get_config_dir", return_value=config_path):
            history_path = get_history_file_path()

        # Directory should be created
        assert config_path.exists()
        assert config_path.is_dir()

        # History file path should be correct
        expected = config_path / "history"
        assert history_path == expected

    def test_get_history_file_path_existing_directory(self, temp_dir):
        """Test history file path with existing directory."""
        config_path = temp_dir / "existing_config"
        config_path.mkdir(parents=True, exist_ok=True)

        with patch("ifcpeek.config.get_config_dir", return_value=config_path):
            history_path = get_history_file_path()

        expected = config_path / "history"
        assert history_path == expected

    def test_get_history_file_path_permission_error(self, temp_dir):
        """Test history file path with permission errors."""
        # Create a read-only directory to simulate permission issues
        readonly_dir = temp_dir / "readonly"
        readonly_dir.mkdir()

        # Make directory read-only (remove write permissions)
        readonly_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)  # r-x------

        config_path = readonly_dir / "ifcpeek"

        with patch("ifcpeek.config.get_config_dir", return_value=config_path):
            try:
                # FIXED: Updated to match the actual error message format
                with pytest.raises(
                    ConfigurationError,
                    match="Failed to create history file path.*Permission denied",
                ):
                    get_history_file_path()
            finally:
                # Restore permissions for cleanup
                readonly_dir.chmod(stat.S_IRWXU)  # rwx------

    def test_get_history_file_path_handles_mkdir_errors(self):
        """Test history file path handles mkdir errors gracefully."""
        mock_config_dir = Mock(spec=Path)
        mock_config_dir.mkdir.side_effect = OSError("Disk full")

        with patch("ifcpeek.config.get_config_dir", return_value=mock_config_dir):
            # FIXED: Updated to match the actual error message format
            with pytest.raises(
                ConfigurationError, match="Failed to create history file path.*OS error"
            ):
                get_history_file_path()


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
        # FIXED: Added all the extensions that are now supported
        extensions = [".ifc", ".IFC", ".Ifc", ".IfC"]

        for ext in extensions:
            ifc_file = temp_dir / f"test{ext}"
            ifc_file.write_text("ISO-10303-21;")

            # Should not raise exception
            result = validate_ifc_file_path(str(ifc_file))
            assert result == ifc_file

            # Clean up for next iteration
            ifc_file.unlink()

    def test_validate_ifc_content_with_unusual_extension(self, temp_dir):
        """Test validation of IFC content with unusual extension."""
        # File has unusual extension but valid IFC content
        ifc_file = temp_dir / "test.model"
        ifc_file.write_text(
            "ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;"
        )

        # Should accept due to valid IFC content
        result = validate_ifc_file_path(str(ifc_file))
        assert result == ifc_file

    def test_validate_relative_path(self, temp_dir):
        """Test validation with relative paths."""
        ifc_file = temp_dir / "relative.ifc"
        ifc_file.write_text("ISO-10303-21;")

        # Change to temp directory to test relative path
        original_cwd = Path.cwd()
        try:
            os.chdir(temp_dir)
            result = validate_ifc_file_path("relative.ifc")
            assert result.name == "relative.ifc"
            assert result.exists()
        finally:
            os.chdir(original_cwd)


class TestCrossPlatformCompatibility:
    """Test cross-platform compatibility."""

    @pytest.mark.parametrize("platform_system", ["Windows", "Darwin", "Linux"])
    def test_config_paths_cross_platform(self, platform_system):
        """Test config paths work across different platforms."""
        with patch("platform.system", return_value=platform_system):
            # Should not raise exceptions on any platform
            config_dir = get_config_dir()
            assert isinstance(config_dir, Path)

            cache_dir = get_cache_dir()
            assert isinstance(cache_dir, Path)

    def test_windows_path_handling(self):
        """Test Windows-specific path handling."""
        with patch("pathlib.Path.home") as mock_home:
            mock_home.return_value = Path("C:/Users/TestUser")

            # Remove XDG variables to force fallback
            env = os.environ.copy()
            env.pop("XDG_STATE_HOME", None)
            env.pop("XDG_CACHE_HOME", None)

            with patch.dict(os.environ, env, clear=True):
                config_dir = get_config_dir()
                cache_dir = get_cache_dir()

            # Verify Windows-appropriate paths
            assert "TestUser" in str(config_dir)
            assert "TestUser" in str(cache_dir)

    def test_path_separator_handling(self, temp_dir):
        """Test that path separators are handled correctly."""
        # Test with various path formats
        ifc_file = temp_dir / "test.ifc"
        ifc_file.write_text("ISO-10303-21;")

        # Test forward slashes (Unix-style)
        unix_style = str(ifc_file).replace("\\", "/")
        result1 = validate_ifc_file_path(unix_style)
        assert result1.exists()

        # Test with Path object
        result2 = validate_ifc_file_path(str(ifc_file))
        assert result2.exists()


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_very_long_paths(self, temp_dir):
        """Test handling of very long file paths."""
        # Create a deeply nested directory structure
        deep_path = temp_dir
        for i in range(10):
            deep_path = deep_path / f"very_long_directory_name_{i}"

        deep_path.mkdir(parents=True)
        ifc_file = deep_path / "test.ifc"
        ifc_file.write_text("ISO-10303-21;")

        # Should handle long paths correctly
        result = validate_ifc_file_path(str(ifc_file))
        assert result == ifc_file

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

    def test_special_characters_in_paths(self, temp_dir):
        """Test handling of special characters in paths."""
        special_chars = ["(", ")", "[", "]", "&", "$", "@"]

        for char in special_chars:
            if char not in str(temp_dir):  # Avoid conflicts with temp dir path
                special_file = temp_dir / f"test{char}file.ifc"
                special_file.write_text("ISO-10303-21;")

                result = validate_ifc_file_path(str(special_file))
                assert result == special_file

                special_file.unlink()  # Clean up

    def test_symlink_handling(self, temp_dir):
        """Test handling of symbolic links."""
        # Create original file
        original = temp_dir / "original.ifc"
        original.write_text("ISO-10303-21;")

        # Create symlink
        symlink = temp_dir / "symlink.ifc"
        try:
            symlink.symlink_to(original)

            # Should resolve symlink correctly
            result = validate_ifc_file_path(str(symlink))
            assert result == symlink
            assert result.exists()

        except OSError:
            # Skip if symlinks not supported (e.g., Windows without admin)
            pytest.skip("Symbolic links not supported on this platform")

    def test_empty_filename(self):
        """Test handling of empty filename."""
        # Empty string creates a Path to current directory, which exists but isn't a file
        with pytest.raises(InvalidIfcFileError, match="is not a file"):
            validate_ifc_file_path("")

    def test_none_filename(self):
        """Test handling of None filename."""
        # FIXED: Now expects TypeError to be raised directly, not wrapped
        with pytest.raises(TypeError, match="expected str, bytes or os.PathLike"):
            validate_ifc_file_path(None)

    def test_whitespace_only_filename(self):
        """Test handling of whitespace-only filename."""
        # Whitespace-only path might resolve to current directory or fail
        with pytest.raises((InvalidIfcFileError, FileNotFoundError)):
            validate_ifc_file_path("   ")

    def test_current_directory_path(self):
        """Test handling of current directory path."""
        # "." resolves to current directory, which exists but isn't a file
        with pytest.raises(InvalidIfcFileError, match="is not a file"):
            validate_ifc_file_path(".")

    def test_parent_directory_path(self):
        """Test handling of parent directory path."""
        # ".." resolves to parent directory, which exists but isn't a file
        with pytest.raises(InvalidIfcFileError, match="is not a file"):
            validate_ifc_file_path("..")


class TestErrorHandling:
    """Test error handling features in config module."""

    def test_debug_output_in_validation(self, temp_dir, capsys):
        """Test that validation produces debug output."""
        ifc_file = temp_dir / "debug_test.ifc"
        ifc_file.write_text("ISO-10303-21;")

        validate_ifc_file_path(str(ifc_file))

        captured = capsys.readouterr()
        debug_output = captured.err  # CHANGED: expect debug in STDERR

        # Should contain debug information
        assert "DEBUG: Validating IFC file path:" in debug_output
        assert "DEBUG: File size:" in debug_output
        assert "DEBUG: File permissions:" in debug_output
        assert "DEBUG: File validation successful:" in debug_output

    def test_comprehensive_file_analysis(self, temp_dir, capsys):
        """Test comprehensive file analysis during validation."""
        # Create file with specific content
        ifc_file = temp_dir / "analysis_test.ifc"
        ifc_content = """ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('Test'),'2;1');
ENDSEC;
DATA;
ENDSEC;
END-ISO-10303-21;"""
        ifc_file.write_text(ifc_content)

        validate_ifc_file_path(str(ifc_file))

        captured = capsys.readouterr()
        debug_output = captured.err  # CHANGED: expect debug in STDERR

        # Should contain file content analysis
        assert "DEBUG: First few lines of file:" in debug_output
        assert "File appears to have valid IFC header" in debug_output

    def test_invalid_content_detection(self, temp_dir, capsys):
        """Test detection of invalid IFC content."""
        # Create file with invalid content but valid extension
        invalid_file = temp_dir / "invalid.ifc"
        invalid_file.write_text("This is not IFC content")

        validate_ifc_file_path(str(invalid_file))  # Should still pass due to extension

        captured = capsys.readouterr()
        debug_output = captured.err  # CHANGED: expect debug in STDERR

        # Should warn about invalid content
        assert "WARNING: File does not start with standard IFC header" in debug_output

    def test_permission_analysis(self, temp_dir, capsys):
        """Test permission analysis in debug output."""
        ifc_file = temp_dir / "permission_test.ifc"
        ifc_file.write_text("ISO-10303-21;")

        validate_ifc_file_path(str(ifc_file))

        captured = capsys.readouterr()
        debug_output = captured.err  # CHANGED: expect debug in STDERR

        # Should include permission information
        assert "DEBUG: File readable:" in debug_output

    def test_traceback_on_unexpected_errors(self, capsys):
        """Test that unexpected errors show full tracebacks."""
        # Mock Path to cause an unexpected error
        with patch("ifcpeek.config.Path") as mock_path:
            mock_path.side_effect = RuntimeError("Unexpected path error")

            try:
                validate_ifc_file_path("test.ifc")
            except InvalidIfcFileError:
                pass  # Expected

            captured = capsys.readouterr()
            debug_output = captured.err  # CHANGED: expect debug in STDERR

            # Should show full traceback
            assert "Full traceback:" in debug_output
            assert "ERROR: Unexpected error during file validation" in debug_output


class TestSystemInformation:
    """Test system information gathering."""

    def test_get_system_info(self):
        """Test system information gathering."""
        from ifcpeek.config import get_system_info

        info = get_system_info()

        # Should contain basic system information
        assert "platform" in info
        assert "python_version" in info
        assert "environment_variables" in info

    def test_print_debug_info(self, capsys):
        """Test debug information printing."""
        from ifcpeek.config import print_debug_info

        print_debug_info()

        captured = capsys.readouterr()
        debug_output = captured.err  # CHANGED: expect debug in STDERR

        # Should contain comprehensive debug information
        assert "IFCPEEK CONFIGURATION DEBUG INFORMATION" in debug_output
        assert "CONFIGURATION PATHS:" in debug_output
