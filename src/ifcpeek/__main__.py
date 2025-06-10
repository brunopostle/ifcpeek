"""Entry point for ifcpeek command."""

import sys
import argparse
import traceback
import os
from .shell import IfcPeek
from .exceptions import IfcPeekError


def main() -> None:
    """Main entry point with comprehensive error handling and debugging."""
    parser = argparse.ArgumentParser(
        prog="ifcpeek",
        description="Interactive shell for querying IFC models",
    )
    parser.add_argument("ifc_file", help="Path to IFC file")
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug output (disabled by default)"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose startup information",
    )
    parser.add_argument(
        "--force-interactive",
        action="store_true",
        help="Force interactive mode even when STDIN/STDOUT are not TTYs (for testing)",
    )
    parser.add_argument(
        "--headers",
        action="store_true",
        help="Include headers in CSV output for value extraction queries",
    )

    try:
        args = parser.parse_args()

        # Set debug environment variable for the shell
        if args.debug:
            os.environ["IFCPEEK_DEBUG"] = "1"

        if args.verbose:
            os.environ["IFCPEEK_VERBOSE"] = "1"

        # Show startup info if verbose or debug mode
        if args.verbose or args.debug:
            print("=" * 60, file=sys.stderr)
            print("IfcPeek - Starting", file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            print(f"Target file: {args.ifc_file}", file=sys.stderr)
            print(f"Python version: {sys.version}", file=sys.stderr)
            print(
                f"Debug mode: {'enabled' if args.debug else 'disabled'}",
                file=sys.stderr,
            )
            if args.force_interactive:
                print("Force interactive mode: enabled", file=sys.stderr)
            print("Error handling and debugging active", file=sys.stderr)
            print("=" * 60, file=sys.stderr)

        # Create and run the IfcPeek with error reporting
        shell = None
        try:
            shell = IfcPeek(args.ifc_file, force_interactive=args.force_interactive)
            shell.headers_enabled = args.headers
            shell.run()

        except IfcPeekError as e:
            print("=" * 60, file=sys.stderr)
            print("IFCPEEK ERROR", file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            print(f"Error: {e}", file=sys.stderr)
            print("\nThis is a known IfcPeek error type.", file=sys.stderr)
            print("Full error details:", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            sys.exit(1)

        except Exception as e:
            print("=" * 60, file=sys.stderr)
            print("UNEXPECTED ERROR", file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            print(f"Unexpected error: {e}", file=sys.stderr)
            print(
                "\nThis is an unexpected error. Please report this issue.",
                file=sys.stderr,
            )
            print("Full error details:", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            sys.exit(1)

    except KeyboardInterrupt:
        print("\nInterrupted by user. Goodbye!", file=sys.stderr)
        sys.exit(0)

    except SystemExit:
        # Re-raise SystemExit (from argparse --help, etc.)
        raise

    except Exception as e:
        print("=" * 60, file=sys.stderr)
        print("CRITICAL ERROR", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(
            f"Critical error during startup: {type(e).__name__}: {e}", file=sys.stderr
        )
        print(
            "\nThis error occurred before IfcPeek could start properly.",
            file=sys.stderr,
        )
        print("Full error details:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
