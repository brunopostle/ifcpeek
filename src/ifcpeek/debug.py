"""Debug utilities for IfcPeek with configurable output."""

import os
import sys


class DebugManager:
    """Manages debug output for IfcPeek with configurable verbosity."""

    def __init__(self):
        # Don't cache the values - always check environment
        pass

    def _check_debug_enabled(self) -> bool:
        """Check if debug mode is enabled via environment variable."""
        return os.environ.get("IFCPEEK_DEBUG", "").lower() in ("1", "true", "yes", "on")

    def _check_verbose_enabled(self) -> bool:
        """Check if verbose mode is enabled via environment variable."""
        return os.environ.get("IFCPEEK_VERBOSE", "").lower() in (
            "1",
            "true",
            "yes",
            "on",
        )

    @property
    def debug_enabled(self) -> bool:
        """Check if debug output is enabled (always checks environment)."""
        return self._check_debug_enabled()

    @property
    def verbose_enabled(self) -> bool:
        """Check if verbose output is enabled (always checks environment)."""
        return self._check_verbose_enabled()

    def enable_debug(self) -> None:
        """Enable debug output."""
        os.environ["IFCPEEK_DEBUG"] = "1"

    def disable_debug(self) -> None:
        """Disable debug output."""
        os.environ.pop("IFCPEEK_DEBUG", None)

    def enable_verbose(self) -> None:
        """Enable verbose output."""
        os.environ["IFCPEEK_VERBOSE"] = "1"

    def disable_verbose(self) -> None:
        """Disable verbose output."""
        os.environ.pop("IFCPEEK_VERBOSE", None)

    def debug_print(self, *args, **kwargs) -> None:
        """Print debug message if debug mode is enabled."""
        if self.debug_enabled:
            print("DEBUG:", *args, file=sys.stderr, **kwargs)

    def verbose_print(self, *args, **kwargs) -> None:
        """Print verbose message if verbose mode is enabled."""
        if self.verbose_enabled or self.debug_enabled:
            print(*args, file=sys.stderr, **kwargs)

    def error_print(self, *args, **kwargs) -> None:
        """Print error message (always shown)."""
        print("ERROR:", *args, file=sys.stderr, **kwargs)

    def warning_print(self, *args, **kwargs) -> None:
        """Print warning message (always shown)."""
        print("WARNING:", *args, file=sys.stderr, **kwargs)


# Global debug manager instance
_debug_manager = DebugManager()


# Convenience functions for global access
def is_debug_enabled() -> bool:
    """Check if debug mode is enabled."""
    return _debug_manager.debug_enabled


def is_verbose_enabled() -> bool:
    """Check if verbose mode is enabled."""
    return _debug_manager.verbose_enabled


def enable_debug() -> None:
    """Enable debug output globally."""
    _debug_manager.enable_debug()


def disable_debug() -> None:
    """Disable debug output globally."""
    _debug_manager.disable_debug()


def enable_verbose() -> None:
    """Enable verbose output globally."""
    _debug_manager.enable_verbose()


def disable_verbose() -> None:
    """Disable verbose output globally."""
    _debug_manager.disable_verbose()


def debug_print(*args, **kwargs) -> None:
    """Print debug message if debug mode is enabled."""
    _debug_manager.debug_print(*args, **kwargs)


def verbose_print(*args, **kwargs) -> None:
    """Print verbose message if verbose or debug mode is enabled."""
    _debug_manager.verbose_print(*args, **kwargs)


def error_print(*args, **kwargs) -> None:
    """Print error message (always shown)."""
    _debug_manager.error_print(*args, **kwargs)


def warning_print(*args, **kwargs) -> None:
    """Print warning message (always shown)."""
    _debug_manager.warning_print(*args, **kwargs)


def get_debug_manager() -> DebugManager:
    """Get the global debug manager instance."""
    return _debug_manager
