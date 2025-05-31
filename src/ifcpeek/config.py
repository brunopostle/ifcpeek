"""Configuration and file path management with controlled debug output."""

import os
import sys
import traceback
from pathlib import Path

from .exceptions import (
    ConfigurationError,
    FileNotFoundError,
    InvalidIfcFileError,
)
from .debug import (
    debug_print,
    verbose_print,
    error_print,
    warning_print,
    is_debug_enabled,
)


def get_config_dir() -> Path:
    """Get XDG-compliant config directory with controlled debug output."""
    try:
        if xdg_state := os.environ.get("XDG_STATE_HOME"):
            config_path = Path(xdg_state) / "ifcpeek"
        else:
            config_path = Path.home() / ".local" / "state" / "ifcpeek"

        # Debug information only if debug mode is enabled
        debug_print(f"Config directory determined: {config_path}")
        debug_print(f"XDG_STATE_HOME: {os.environ.get('XDG_STATE_HOME', 'Not set')}")
        debug_print(f"Home directory: {Path.home()}")

        return config_path

    except Exception as e:
        error_context = {
            "XDG_STATE_HOME": os.environ.get("XDG_STATE_HOME", "Not set"),
            "HOME": os.environ.get("HOME", "Not set"),
            "error_type": type(e).__name__,
        }

        error_print("Failed to determine configuration directory")
        debug_print("DEBUG INFORMATION:")
        for key, value in error_context.items():
            debug_print(f"  {key}: {value}")
        debug_print("Full traceback:")
        if is_debug_enabled():
            traceback.print_exc(file=sys.stderr)

        raise ConfigurationError(
            f"Failed to determine config directory: {e}", system_info=error_context
        ) from e


def get_history_file_path() -> Path:
    """Get history file path with controlled debug output, creating directory if needed."""
    try:
        config_dir = get_config_dir()

        debug_print(f"Creating config directory if needed: {config_dir}")
        debug_print(f"Directory exists: {config_dir.exists()}")
        debug_print(
            f"Directory is dir: {config_dir.is_dir() if config_dir.exists() else 'N/A'}"
        )

        # Create directory with error handling
        try:
            config_dir.mkdir(parents=True, exist_ok=True)
            debug_print("Directory creation successful")
        except PermissionError as perm_error:
            error_print(f"Permission denied creating directory: {config_dir}")
            debug_print(f"Permission error: {perm_error}")
            raise ConfigurationError(
                f"Failed to create history file path: Permission denied creating config directory: {config_dir}",
                config_path=str(config_dir),
            ) from perm_error
        except OSError as os_error:
            error_print(f"OS error creating directory: {config_dir}")
            debug_print(f"OS error: {os_error}")
            raise ConfigurationError(
                f"Failed to create history file path: OS error creating config directory: {config_dir}",
                config_path=str(config_dir),
            ) from os_error

        history_path = config_dir / "history"
        debug_print(f"History file path: {history_path}")

        return history_path

    except ConfigurationError:
        # Re-raise configuration errors from get_config_dir
        raise
    except Exception as e:
        error_print("Unexpected error creating history file path")
        debug_print(f"Error type: {type(e).__name__}")
        debug_print(f"Error message: {e}")
        debug_print("Full traceback:")
        if is_debug_enabled():
            traceback.print_exc(file=sys.stderr)

        raise ConfigurationError(f"Failed to create history file path: {e}") from e


def validate_ifc_file_path(file_path: str) -> Path:
    """Validate and return Path object for IFC file with controlled debug output."""
    # Handle None input early to avoid Path() TypeError
    if file_path is None:
        raise TypeError("expected str, bytes or os.PathLike object, not NoneType")

    try:
        debug_print(f"Validating IFC file path: {file_path}")

        # Convert to Path object
        path = Path(file_path)
        debug_print(f"Resolved path: {path}")
        debug_print(f"Absolute path: {path.resolve()}")

        # Check if file exists
        if not path.exists():
            error_context = {
                "provided_path": file_path,
                "resolved_path": str(path.resolve()),
                "parent_exists": path.parent.exists(),
                "current_dir": str(Path.cwd()),
            }

            error_print("File does not exist")
            debug_print("DEBUG INFORMATION:")
            for key, value in error_context.items():
                debug_print(f"  {key}: {value}")

            raise FileNotFoundError(
                f"File '{file_path}' not found", file_path=file_path
            )

        # Check if it's actually a file (not a directory)
        if not path.is_file():
            error_context = {
                "path": str(path),
                "exists": path.exists(),
                "is_dir": path.is_dir(),
                "is_file": path.is_file(),
                "is_symlink": path.is_symlink(),
            }

            error_print("Path exists but is not a file")
            debug_print("DEBUG INFORMATION:")
            for key, value in error_context.items():
                debug_print(f"  {key}: {value}")

            raise InvalidIfcFileError(
                f"'{file_path}' is not a file", file_path=file_path
            )

        # Get file statistics for debugging
        try:
            stat = path.stat()
            file_size = stat.st_size
            file_mode = oct(stat.st_mode)
            debug_print(f"File size: {file_size} bytes")
            debug_print(f"File permissions: {file_mode}")
            debug_print(f"File readable: {os.access(path, os.R_OK)}")
        except Exception as stat_error:
            warning_print(f"Could not get file statistics: {stat_error}")
            file_size = None

        # Basic extension check with validation - case insensitive
        valid_extensions = [".ifc", ".IFC", ".Ifc", ".IfC"]
        if path.suffix not in valid_extensions:
            error_context = {
                "file_path": file_path,
                "detected_extension": path.suffix,
                "valid_extensions": valid_extensions,
                "file_size": file_size,
            }

            error_print("Invalid file extension")
            debug_print("DEBUG INFORMATION:")
            for key, value in error_context.items():
                debug_print(f"  {key}: {value}")

            # Try to read first few bytes to check for IFC header
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    first_line = f.readline().strip()
                    debug_print(f"First line of file: {first_line[:50]}...")

                    if first_line.startswith("ISO-10303-21"):
                        warning_print("File appears to be IFC format despite extension")
                        verbose_print("Proceeding with validation...")
                        return path
                    else:
                        debug_print("File does not appear to contain IFC data")
            except Exception as read_error:
                debug_print(f"Could not read file for format validation: {read_error}")

            raise InvalidIfcFileError(
                f"'{file_path}' does not appear to be an IFC file (extension: {path.suffix})",
                file_path=file_path,
                file_size=file_size,
                error_type="InvalidExtension",
            )

        # Additional file content validation
        try:
            # Try to read the first few lines to validate IFC format
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                first_lines = []
                for i, line in enumerate(f):
                    first_lines.append(line.strip())
                    if i >= 5:  # Read first 6 lines
                        break

                debug_print("First few lines of file:")
                for i, line in enumerate(first_lines):
                    debug_print(f"  Line {i+1}: {line[:100]}...")

                # Check for IFC header
                if not first_lines or not first_lines[0].startswith("ISO-10303-21"):
                    warning_print("File does not start with standard IFC header")
                    debug_print("This might not be a valid IFC file")
                else:
                    debug_print("File appears to have valid IFC header")

        except UnicodeDecodeError as unicode_error:
            warning_print(f"Unicode decode error reading file: {unicode_error}")
            debug_print("File might be binary or have encoding issues")
        except Exception as read_error:
            warning_print(f"Could not validate file content: {read_error}")
            debug_print("File might be locked or have permission issues")

        debug_print(f"File validation successful: {path}")
        return path

    except (FileNotFoundError, InvalidIfcFileError, TypeError):
        # Re-raise our custom exceptions and TypeError
        raise
    except Exception as e:
        # Handle any other unexpected errors
        error_context = {
            "provided_path": file_path,
            "error_type": type(e).__name__,
            "error_message": str(e),
        }

        error_print("Unexpected error during file validation")
        debug_print("DEBUG INFORMATION:")
        for key, value in error_context.items():
            debug_print(f"  {key}: {value}")
        debug_print("Full traceback:")
        if is_debug_enabled():
            traceback.print_exc(file=sys.stderr)

        raise InvalidIfcFileError(
            f"Unexpected error validating file '{file_path}': {e}",
            file_path=file_path,
            error_type="UnexpectedError",
        ) from e


def print_debug_info():
    """Print basic debug information for troubleshooting (only if debug enabled)."""
    if not is_debug_enabled():
        print(
            "Debug mode is disabled. Use --debug to enable detailed information.",
            file=sys.stderr,
        )
        return

    print("=" * 60, file=sys.stderr)
    print("IFCPEEK CONFIGURATION DEBUG INFORMATION", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    try:
        import platform

        print(f"Platform: {platform.platform()}", file=sys.stderr)
        print(f"Python version: {sys.version}", file=sys.stderr)
        print(f"Current directory: {Path.cwd()}", file=sys.stderr)
        print(f"Home directory: {Path.home()}", file=sys.stderr)

        print("\nCONFIGURATION PATHS:", file=sys.stderr)
        try:
            config_dir = get_config_dir()
            print(f"Config directory: {config_dir}", file=sys.stderr)
            print(f"Config dir exists: {config_dir.exists()}", file=sys.stderr)
        except Exception as e:
            print(f"Config directory error: {e}", file=sys.stderr)

        try:
            history_path = get_history_file_path()
            print(f"History file path: {history_path}", file=sys.stderr)
            print(f"History file exists: {history_path.exists()}", file=sys.stderr)
        except Exception as e:
            print(f"History file path error: {e}", file=sys.stderr)

    except Exception as e:
        error_print(f"Could not print debug information: {e}")
        if is_debug_enabled():
            traceback.print_exc(file=sys.stderr)

    print("=" * 60, file=sys.stderr)


if __name__ == "__main__":
    # Run debug information when module is executed directly
    print_debug_info()
