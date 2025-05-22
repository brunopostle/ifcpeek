"""Configuration and file path management with error handling."""
import os
import sys
import traceback
from pathlib import Path
from typing import Optional

from .exceptions import (
    ConfigurationError,
    FileNotFoundError,
    InvalidIfcFileError,
)


def get_config_dir() -> Path:
    """Get XDG-compliant config directory with error handling."""
    try:
        if xdg_state := os.environ.get("XDG_STATE_HOME"):
            config_path = Path(xdg_state) / "ifcpeek"
        else:
            config_path = Path.home() / ".local" / "state" / "ifcpeek"

        # Debugging information to STDERR
        print(f"DEBUG: Config directory determined: {config_path}", file=sys.stderr)
        print(
            f"DEBUG: XDG_STATE_HOME: {os.environ.get('XDG_STATE_HOME', 'Not set')}",
            file=sys.stderr,
        )
        print(f"DEBUG: Home directory: {Path.home()}", file=sys.stderr)

        return config_path

    except Exception as e:
        error_context = {
            "XDG_STATE_HOME": os.environ.get("XDG_STATE_HOME", "Not set"),
            "HOME": os.environ.get("HOME", "Not set"),
            "error_type": type(e).__name__,
        }

        print("ERROR: Failed to determine configuration directory", file=sys.stderr)
        print("DEBUG INFORMATION:", file=sys.stderr)
        for key, value in error_context.items():
            print(f"  {key}: {value}", file=sys.stderr)
        print("Full traceback:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)

        raise ConfigurationError(
            f"Failed to determine config directory: {e}", system_info=error_context
        ) from e


def get_history_file_path() -> Path:
    """Get history file path with error handling, creating directory if needed."""
    try:
        config_dir = get_config_dir()

        print(
            f"DEBUG: Creating config directory if needed: {config_dir}", file=sys.stderr
        )
        print(f"DEBUG: Directory exists: {config_dir.exists()}", file=sys.stderr)
        print(
            f"DEBUG: Directory is dir: {config_dir.is_dir() if config_dir.exists() else 'N/A'}",
            file=sys.stderr,
        )

        # Create directory with error handling
        try:
            config_dir.mkdir(parents=True, exist_ok=True)
            print(f"DEBUG: Directory creation successful", file=sys.stderr)
        except PermissionError as perm_error:
            print(
                f"ERROR: Permission denied creating directory: {config_dir}",
                file=sys.stderr,
            )
            print(f"Permission error: {perm_error}", file=sys.stderr)
            raise ConfigurationError(
                f"Failed to create history file path: Permission denied creating config directory: {config_dir}",
                config_path=str(config_dir),
            ) from perm_error
        except OSError as os_error:
            print(f"ERROR: OS error creating directory: {config_dir}", file=sys.stderr)
            print(f"OS error: {os_error}", file=sys.stderr)
            raise ConfigurationError(
                f"Failed to create history file path: OS error creating config directory: {config_dir}",
                config_path=str(config_dir),
            ) from os_error

        history_path = config_dir / "history"
        print(f"DEBUG: History file path: {history_path}", file=sys.stderr)

        return history_path

    except ConfigurationError:
        # Re-raise configuration errors from get_config_dir
        raise
    except Exception as e:
        print("ERROR: Unexpected error creating history file path", file=sys.stderr)
        print(f"Error type: {type(e).__name__}", file=sys.stderr)
        print(f"Error message: {e}", file=sys.stderr)
        print("Full traceback:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)

        raise ConfigurationError(f"Failed to create history file path: {e}") from e


def get_cache_dir() -> Path:
    """Get cache directory for temporary files with debugging."""
    try:
        if xdg_cache := os.environ.get("XDG_CACHE_HOME"):
            cache_path = Path(xdg_cache) / "ifcpeek"
        else:
            cache_path = Path.home() / ".cache" / "ifcpeek"

        print(f"DEBUG: Cache directory determined: {cache_path}", file=sys.stderr)
        print(
            f"DEBUG: XDG_CACHE_HOME: {os.environ.get('XDG_CACHE_HOME', 'Not set')}",
            file=sys.stderr,
        )

        return cache_path

    except Exception as e:
        print(
            f"WARNING: Error determining cache directory: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        print("Full traceback:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)

        # Fallback to a basic path
        fallback_path = Path.home() / ".ifcpeek_cache"
        print(f"Using fallback cache directory: {fallback_path}", file=sys.stderr)
        return fallback_path


def validate_ifc_file_path(file_path: str) -> Path:
    """Validate and return Path object for IFC file with comprehensive error handling."""
    # Handle None input early to avoid Path() TypeError
    if file_path is None:
        raise TypeError("expected str, bytes or os.PathLike object, not NoneType")

    try:
        print(f"DEBUG: Validating IFC file path: {file_path}", file=sys.stderr)

        # Convert to Path object
        path = Path(file_path)
        print(f"DEBUG: Resolved path: {path}", file=sys.stderr)
        print(f"DEBUG: Absolute path: {path.resolve()}", file=sys.stderr)

        # Check if file exists
        if not path.exists():
            error_context = {
                "provided_path": file_path,
                "resolved_path": str(path.resolve()),
                "parent_exists": path.parent.exists(),
                "current_dir": str(Path.cwd()),
            }

            print("ERROR: File does not exist", file=sys.stderr)
            print("DEBUG INFORMATION:", file=sys.stderr)
            for key, value in error_context.items():
                print(f"  {key}: {value}", file=sys.stderr)

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

            print("ERROR: Path exists but is not a file", file=sys.stderr)
            print("DEBUG INFORMATION:", file=sys.stderr)
            for key, value in error_context.items():
                print(f"  {key}: {value}", file=sys.stderr)

            raise InvalidIfcFileError(
                f"'{file_path}' is not a file", file_path=file_path
            )

        # Get file statistics for debugging
        try:
            stat = path.stat()
            file_size = stat.st_size
            file_mode = oct(stat.st_mode)
            print(f"DEBUG: File size: {file_size} bytes", file=sys.stderr)
            print(f"DEBUG: File permissions: {file_mode}", file=sys.stderr)
            print(f"DEBUG: File readable: {os.access(path, os.R_OK)}", file=sys.stderr)
        except Exception as stat_error:
            print(
                f"WARNING: Could not get file statistics: {stat_error}", file=sys.stderr
            )
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

            print("ERROR: Invalid file extension", file=sys.stderr)
            print("DEBUG INFORMATION:", file=sys.stderr)
            for key, value in error_context.items():
                print(f"  {key}: {value}", file=sys.stderr)

            # Try to read first few bytes to check for IFC header
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    first_line = f.readline().strip()
                    print(
                        f"DEBUG: First line of file: {first_line[:50]}...",
                        file=sys.stderr,
                    )

                    if first_line.startswith("ISO-10303-21"):
                        print(
                            "WARNING: File appears to be IFC format despite extension",
                            file=sys.stderr,
                        )
                        print("Proceeding with validation...", file=sys.stderr)
                        return path
                    else:
                        print(
                            "File does not appear to contain IFC data", file=sys.stderr
                        )
            except Exception as read_error:
                print(
                    f"Could not read file for format validation: {read_error}",
                    file=sys.stderr,
                )

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

                print("DEBUG: First few lines of file:", file=sys.stderr)
                for i, line in enumerate(first_lines):
                    print(f"  Line {i+1}: {line[:100]}...", file=sys.stderr)

                # Check for IFC header
                if not first_lines or not first_lines[0].startswith("ISO-10303-21"):
                    print(
                        "WARNING: File does not start with standard IFC header",
                        file=sys.stderr,
                    )
                    print("This might not be a valid IFC file", file=sys.stderr)
                else:
                    print("File appears to have valid IFC header", file=sys.stderr)

        except UnicodeDecodeError as unicode_error:
            print(
                f"WARNING: Unicode decode error reading file: {unicode_error}",
                file=sys.stderr,
            )
            print("File might be binary or have encoding issues", file=sys.stderr)
        except Exception as read_error:
            print(
                f"WARNING: Could not validate file content: {read_error}",
                file=sys.stderr,
            )
            print("File might be locked or have permission issues", file=sys.stderr)

        print(f"DEBUG: File validation successful: {path}", file=sys.stderr)
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

        print("ERROR: Unexpected error during file validation", file=sys.stderr)
        print("DEBUG INFORMATION:", file=sys.stderr)
        for key, value in error_context.items():
            print(f"  {key}: {value}", file=sys.stderr)
        print("Full traceback:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)

        raise InvalidIfcFileError(
            f"Unexpected error validating file '{file_path}': {e}",
            file_path=file_path,
            error_type="UnexpectedError",
        ) from e


def create_directory_with_error_handling(
    directory_path: Path, purpose: str = "directory"
) -> bool:
    """Create directory with comprehensive error handling and debugging.

    Args:
        directory_path: Path to directory to create
        purpose: Description of directory purpose for error messages

    Returns:
        True if directory was created or already exists, False otherwise

    Raises:
        ConfigurationError: If directory cannot be created due to critical issues
    """
    try:
        print(f"DEBUG: Creating {purpose}: {directory_path}", file=sys.stderr)
        print(f"DEBUG: Directory exists: {directory_path.exists()}", file=sys.stderr)

        if directory_path.exists():
            if directory_path.is_dir():
                print(f"DEBUG: {purpose.capitalize()} already exists", file=sys.stderr)
                return True
            else:
                print(
                    f"ERROR: Path exists but is not a directory: {directory_path}",
                    file=sys.stderr,
                )
                raise ConfigurationError(
                    f"Path exists but is not a directory: {directory_path}",
                    config_path=str(directory_path),
                )

        # Attempt to create directory
        directory_path.mkdir(parents=True, exist_ok=True)
        print(f"DEBUG: {purpose.capitalize()} created successfully", file=sys.stderr)

        # Verify creation
        if not directory_path.exists() or not directory_path.is_dir():
            raise ConfigurationError(
                f"Directory creation appeared to succeed but directory does not exist: {directory_path}",
                config_path=str(directory_path),
            )

        return True

    except PermissionError as perm_error:
        error_context = {
            "directory_path": str(directory_path),
            "parent_path": str(directory_path.parent),
            "parent_exists": directory_path.parent.exists(),
            "parent_writable": os.access(directory_path.parent, os.W_OK)
            if directory_path.parent.exists()
            else False,
        }

        print(f"ERROR: Permission denied creating {purpose}", file=sys.stderr)
        print("DEBUG INFORMATION:", file=sys.stderr)
        for key, value in error_context.items():
            print(f"  {key}: {value}", file=sys.stderr)
        print("Full traceback:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)

        raise ConfigurationError(
            f"Permission denied creating {purpose}: {directory_path}",
            config_path=str(directory_path),
            system_info=error_context,
        ) from perm_error

    except OSError as os_error:
        error_context = {
            "directory_path": str(directory_path),
            "error_code": getattr(os_error, "errno", "Unknown"),
            "error_message": str(os_error),
        }

        print(f"ERROR: OS error creating {purpose}", file=sys.stderr)
        print("DEBUG INFORMATION:", file=sys.stderr)
        for key, value in error_context.items():
            print(f"  {key}: {value}", file=sys.stderr)
        print("Full traceback:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)

        # Check for common OS errors
        if "disk full" in str(os_error).lower() or "no space" in str(os_error).lower():
            error_context["suggestion"] = "Free up disk space and try again"
        elif "read-only" in str(os_error).lower():
            error_context["suggestion"] = "Check if filesystem is mounted read-only"

        raise ConfigurationError(
            f"OS error creating {purpose}: {directory_path} - {os_error}",
            config_path=str(directory_path),
            system_info=error_context,
        ) from os_error

    except Exception as e:
        print(
            f"ERROR: Unexpected error creating {purpose}: {directory_path}",
            file=sys.stderr,
        )
        print(f"Error type: {type(e).__name__}", file=sys.stderr)
        print(f"Error message: {e}", file=sys.stderr)
        print("Full traceback:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)

        raise ConfigurationError(
            f"Unexpected error creating {purpose}: {directory_path} - {e}",
            config_path=str(directory_path),
        ) from e


def get_system_info() -> dict:
    """Get system information for debugging purposes.

    Returns:
        Dictionary containing system information
    """
    try:
        import platform
        import sys

        system_info = {
            "platform": platform.platform(),
            "system": platform.system(),
            "machine": platform.machine(),
            "python_version": sys.version,
            "python_executable": sys.executable,
            "current_working_directory": str(Path.cwd()),
            "home_directory": str(Path.home()),
            "environment_variables": {
                "HOME": os.environ.get("HOME", "Not set"),
                "XDG_STATE_HOME": os.environ.get("XDG_STATE_HOME", "Not set"),
                "XDG_CACHE_HOME": os.environ.get("XDG_CACHE_HOME", "Not set"),
                "PATH": os.environ.get("PATH", "Not set")[:200] + "..."
                if len(os.environ.get("PATH", "")) > 200
                else os.environ.get("PATH", "Not set"),
            },
        }

        return system_info

    except Exception as e:
        print(f"WARNING: Could not gather system information: {e}", file=sys.stderr)
        return {"error": f"Could not gather system info: {e}"}


def print_debug_info():
    """Print comprehensive debug information for troubleshooting."""
    print("=" * 60, file=sys.stderr)
    print("IFCPEEK CONFIGURATION DEBUG INFORMATION", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    try:
        system_info = get_system_info()

        for key, value in system_info.items():
            if isinstance(value, dict):
                print(f"{key.upper()}:", file=sys.stderr)
                for sub_key, sub_value in value.items():
                    print(f"  {sub_key}: {sub_value}", file=sys.stderr)
            else:
                print(f"{key}: {value}", file=sys.stderr)

        print("\nCONFIGURATION PATHS:", file=sys.stderr)
        try:
            config_dir = get_config_dir()
            print(f"Config directory: {config_dir}", file=sys.stderr)
            print(f"Config dir exists: {config_dir.exists()}", file=sys.stderr)
        except Exception as e:
            print(f"Config directory error: {e}", file=sys.stderr)

        try:
            cache_dir = get_cache_dir()
            print(f"Cache directory: {cache_dir}", file=sys.stderr)
            print(f"Cache dir exists: {cache_dir.exists()}", file=sys.stderr)
        except Exception as e:
            print(f"Cache directory error: {e}", file=sys.stderr)

        try:
            history_path = get_history_file_path()
            print(f"History file path: {history_path}", file=sys.stderr)
            print(f"History file exists: {history_path.exists()}", file=sys.stderr)
        except Exception as e:
            print(f"History file path error: {e}", file=sys.stderr)

    except Exception as e:
        print(f"ERROR: Could not print debug information: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)

    print("=" * 60, file=sys.stderr)


if __name__ == "__main__":
    # Run debug information when module is executed directly
    print_debug_info()
