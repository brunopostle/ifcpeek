"""
IfcPeek - Interactive command-line shell for querying IFC models.

IfcPeek provides a Unix shell-like interface for exploring and filtering
IFC entities using IfcOpenShell's selector syntax, with professional-grade
error handling, full Python tracebacks, signal management, and tab completion.
"""

__version__ = "1.0.0"
__author__ = "Bruno Postle"
__email__ = "bruno@postle.net"
__license__ = "GPLv3"


# Import main classes for convenience
try:
    from .exceptions import (
        IfcPeekError,
        FileNotFoundError,
        InvalidIfcFileError,
        QueryExecutionError,
        ConfigurationError,
    )
    from .shell import IfcPeek
    from .formatters import StepHighlighter, format_query_results

    __all__ = [
        "__version__",
        "IfcPeek",
        "IfcCompletionCache",
        "IfcValueCompleter",
        "IfcPeekError",
        "FileNotFoundError",
        "InvalidIfcFileError",
        "QueryExecutionError",
        "ConfigurationError",
        "StepHighlighter",
        "format_query_results",
    ]

    # features
    FEATURES = [
        "Full Python tracebacks for debugging",
        "Professional signal handling (SIGINT/SIGTERM)",
        "Comprehensive debug information",
        "Intelligent error recovery",
        "Context-rich exception classes",
        "File validation",
        "Proper STDOUT/STDERR separation",
        "Configurable debug output",
        "Tab completion for value extraction queries",
        "Model-aware property set suggestions",
        "Context-sensitive attribute completions",
        "Partial matching support",
    ]

    def print_features():
        """Print information about features."""
        import sys

        print(f"IfcPeek v{__version__}", file=sys.stderr)
        print("=" * 50, file=sys.stderr)
        print("Features:", file=sys.stderr)
        for feature in FEATURES:
            print(f"  • {feature}", file=sys.stderr)
        print("=" * 50, file=sys.stderr)
        print("For more information, run: python -m ifcpeek --help", file=sys.stderr)

except ImportError as e:
    # Graceful handling of import errors during development
    import sys

    print(f"WARNING: Import error in IfcPeek package: {e}", file=sys.stderr)
    print(
        "This may be expected during development or if dependencies are missing.",
        file=sys.stderr,
    )

    # Minimal fallback exports
    __all__ = ["__version__"]

    def print_features():
        import sys

        print(f"IfcPeek Edition v{__version__} (Import Error)", file=sys.stderr)
        print(
            "Some features may not be available due to missing dependencies.",
            file=sys.stderr,
        )


# Package-level debug information
def get_package_info():
    """Get comprehensive package information for debugging."""
    import sys
    from pathlib import Path

    try:
        package_info = {
            "name": "ifcpeek",
            "version": __version__,
            "author": __author__,
            "license": __license__,
            "python_version": sys.version,
            "package_location": str(Path(__file__).parent),
            "features": len(FEATURES),
            "available_modules": [],
        }

        # Check which modules are available
        modules_to_check = ["shell", "exceptions", "config", "__main__", "completion"]

        for module_name in modules_to_check:
            try:
                __import__(f"ifcpeek.{module_name}")
                package_info["available_modules"].append(module_name)
            except ImportError:
                pass

        return package_info

    except Exception as e:
        return {"error": f"Could not gather package info: {e}"}


# Make features available at package level
if __name__ == "__main__":
    print_features()
