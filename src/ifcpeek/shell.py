import sys
import signal
import traceback
from pathlib import Path
import ifcopenshell
import ifcopenshell.util.selector
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.shortcuts import print_formatted_text

from .config import validate_ifc_file_path, get_history_file_path
from .exceptions import InvalidIfcFileError, ConfigurationError

# Dependency availability flags - always True since dependencies are required
PROMPT_TOOLKIT_AVAILABLE = True
IFCOPENSHELL_AVAILABLE = True


class IfcPeek:
    """Interactive IFC query shell with error handling and signal support."""

    # Built-in commands mapping (IRC-style with forward slashes)
    BUILTIN_COMMANDS = {
        "/help": "_show_help",
        "/exit": "_exit",
        "/quit": "_exit",
    }

    def __init__(self, ifc_file_path: str) -> None:
        """Initialize shell with IFC model and error handling."""
        print(f"IfcPeek initializing with file: {ifc_file_path}", file=sys.stderr)

        # Validate the file path and resolve to absolute path
        try:
            validated_path = validate_ifc_file_path(ifc_file_path)
            self.ifc_file_path = validated_path.resolve()
            print(f"File validated: {self.ifc_file_path}", file=sys.stderr)
        except Exception as e:
            print(
                f"ERROR: File validation failed for '{ifc_file_path}'", file=sys.stderr
            )
            print(f"Error details: {type(e).__name__}: {e}", file=sys.stderr)
            print("\nFull traceback:", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            raise

        # Load the IFC model
        try:
            self.model = self._load_model()
            print(
                f"IFC model loaded successfully (Schema: {getattr(self.model, 'schema', 'Unknown')})",
                file=sys.stderr,
            )
        except Exception as e:
            print(
                f"ERROR: Failed to load IFC model from '{self.ifc_file_path.name}'",
                file=sys.stderr,
            )
            print(f"Error details: {type(e).__name__}: {e}", file=sys.stderr)
            print("\nFull traceback:", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            raise

        # Create the prompt session
        try:
            self.session = self._create_session()
        except ConfigurationError:
            # Re-raise ConfigurationError for critical issues
            raise
        except Exception as e:
            print(
                f"WARNING: Session creation encountered issues: {type(e).__name__}: {e}",
                file=sys.stderr,
            )
            print("Continuing with fallback input mode...", file=sys.stderr)
            self.session = None

        # Setup signal handlers for graceful operation
        self._setup_signal_handlers()

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful operation."""
        try:
            # SIGINT (Ctrl-C) - return to prompt instead of crashing
            def sigint_handler(signum, frame):
                print("\n(Use Ctrl-D to exit, or type /exit)", file=sys.stderr)
                # Don't raise KeyboardInterrupt, just print message and continue
                return

            # SIGTERM - clean exit
            def sigterm_handler(signum, frame):
                print(
                    "\nReceived termination signal. Shutting down gracefully...",
                    file=sys.stderr,
                )
                print("Shell session ended.", file=sys.stderr)
                sys.exit(0)

            signal.signal(signal.SIGINT, sigint_handler)
            signal.signal(signal.SIGTERM, sigterm_handler)

            print("Signal handlers configured for graceful operation", file=sys.stderr)

        except Exception as e:
            print(
                f"WARNING: Could not setup signal handlers: {type(e).__name__}: {e}",
                file=sys.stderr,
            )
            print("Continuing without custom signal handling...", file=sys.stderr)

    def _load_model(self):
        """Load IFC model with comprehensive error handling and debugging info."""
        try:
            print(f"Loading IFC model from: {self.ifc_file_path}", file=sys.stderr)
            print(
                f"File size: {self.ifc_file_path.stat().st_size} bytes", file=sys.stderr
            )
            print(
                f"File permissions: {oct(self.ifc_file_path.stat().st_mode)[-3:]}",
                file=sys.stderr,
            )

            model = ifcopenshell.open(str(self.ifc_file_path))

            # Basic validation - ensure the model was loaded
            if model is None:
                raise InvalidIfcFileError(
                    f"IfcOpenShell returned None when loading '{self.ifc_file_path.name}' - "
                    f"file may be corrupted or not a valid IFC file"
                )

            # Additional model validation
            try:
                schema = getattr(model, "schema", "Unknown")
                print(f"Model schema detected: {schema}", file=sys.stderr)

                # Try to get basic entity count for validation
                total_entities = len([e for e in model])
                print(f"Total entities in model: {total_entities}", file=sys.stderr)

                if total_entities == 0:
                    print("WARNING: Model contains no entities", file=sys.stderr)

            except Exception as validation_error:
                print(
                    f"WARNING: Model validation checks failed: {validation_error}",
                    file=sys.stderr,
                )
                print(
                    "Continuing with potentially incomplete model information...",
                    file=sys.stderr,
                )

            return model

        except Exception as e:
            # Error reporting with full debugging information
            error_context = {
                "file_path": str(self.ifc_file_path),
                "file_exists": self.ifc_file_path.exists(),
                "file_size": self.ifc_file_path.stat().st_size
                if self.ifc_file_path.exists()
                else "N/A",
                "file_readable": self.ifc_file_path.is_file()
                and self.ifc_file_path.stat().st_mode,
                "error_type": type(e).__name__,
                "error_message": str(e),
            }

            print("=" * 60, file=sys.stderr)
            print("IFC MODEL LOADING ERROR - DEBUG INFORMATION", file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            for key, value in error_context.items():
                print(f"{key}: {value}", file=sys.stderr)
            print("=" * 60, file=sys.stderr)

            # Provide more specific error messages for common issues
            error_msg = f"Failed to load IFC file '{self.ifc_file_path.name}': {str(e)}"

            error_str_lower = str(e).lower()
            exception_type = type(e).__name__

            # Add specific hints based on exception types and messages
            if isinstance(e, ValueError) and (
                "not a valid ifc file" in error_str_lower or "parse" in error_str_lower
            ):
                error_msg += "\n\nDEBUG: File does not contain valid IFC data or has parsing errors."
                error_msg += f"\nFile size: {error_context['file_size']} bytes"
                error_msg += "\nSuggestions:"
                error_msg += (
                    "\n  - Verify the file is a valid IFC file (ISO-10303-21 format)"
                )
                error_msg += "\n  - Check if the file was completely downloaded/copied"
                error_msg += (
                    "\n  - Try opening the file in a text editor to verify IFC header"
                )

            elif isinstance(e, PermissionError):
                error_msg += "\n\nDEBUG: Permission denied - check file access rights"
                error_msg += f"\nFile permissions: {error_context.get('file_readable', 'Unknown')}"
                error_msg += "\nSuggestions:"
                error_msg += "\n  - Check file permissions with 'ls -l' (Unix) or file properties (Windows)"
                error_msg += "\n  - Ensure the user has read access to the file"
                error_msg += "\n  - Try running with appropriate permissions"

            elif isinstance(e, (IOError, OSError)) and ("corrupt" in error_str_lower):
                error_msg += "\n\nDEBUG: File appears to be corrupted or incomplete"
                error_msg += f"\nFile size: {error_context['file_size']} bytes"
                error_msg += "\nSuggestions:"
                error_msg += "\n  - Re-download or re-copy the original file"
                error_msg += "\n  - Check available disk space"
                error_msg += "\n  - Verify file integrity with the source"

            elif isinstance(e, RuntimeError) and ("truncat" in error_str_lower):
                error_msg += "\n\nDEBUG: File appears to be incomplete"
                error_msg += f"\nFile size: {error_context['file_size']} bytes"
                error_msg += "\nSuggestions:"
                error_msg += "\n  - Re-download or re-copy the original file"
                error_msg += "\n  - Check if the file transfer was interrupted"
                error_msg += "\n  - Verify file integrity with the source"

            elif "memory" in error_str_lower or "out of memory" in error_str_lower:
                error_msg += "\n\nDEBUG: Insufficient memory to load the model"
                error_msg += f"\nFile size: {error_context['file_size']} bytes"
                error_msg += "\nSuggestions:"
                error_msg += "\n  - Close other applications to free memory"
                error_msg += "\n  - Try with a machine with more RAM"
                error_msg += "\n  - Consider using IFC file optimization tools"

            print(f"\nERROR SUMMARY: {error_msg}", file=sys.stderr)
            print("\nFull Python traceback:", file=sys.stderr)
            print("-" * 40, file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            print("-" * 40, file=sys.stderr)

            raise InvalidIfcFileError(error_msg) from e

    def _create_session(self):
        """Create prompt_toolkit session."""
        try:
            # Get history file path - this creates the directory if needed
            history_path = get_history_file_path()
            print(f"Setting up command history at: {history_path}", file=sys.stderr)

            # Create FileHistory object
            file_history = FileHistory(str(history_path))

            # Create PromptSession with history
            session = PromptSession(history=file_history)

            print(f"Command history initialized successfully", file=sys.stderr)
            return session

        except ConfigurationError:
            # Re-raise configuration errors (from get_history_file_path)
            print(
                "CRITICAL: Configuration error during session creation", file=sys.stderr
            )
            traceback.print_exc(file=sys.stderr)
            raise

        except (PermissionError, OSError) as e:
            # Handle file system permission errors with detailed debugging
            error_str = str(e).lower()

            print(
                f"ERROR: Session creation failed due to filesystem issue",
                file=sys.stderr,
            )
            print(f"Error type: {type(e).__name__}", file=sys.stderr)
            print(f"Error message: {e}", file=sys.stderr)

            if any(
                phrase in error_str
                for phrase in [
                    "permission denied",
                    "disk full",
                    "read-only",
                    "access denied",
                ]
            ):
                # Critical configuration errors should be raised
                print(
                    "This is a critical configuration issue that prevents proper operation.",
                    file=sys.stderr,
                )
                print("Full traceback:", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                raise ConfigurationError(
                    f"Failed to set up command history: {e}"
                ) from e

            # For other OS errors, fall back gracefully
            print(
                f"Warning: Could not create prompt session with history: {e}",
                file=sys.stderr,
            )
            print(
                "Falling back to basic input mode (history will not be saved)",
                file=sys.stderr,
            )
            print("Full error details:", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return None

        except Exception as e:
            # For other errors (like non-terminal environment), fall back gracefully
            print(
                f"Warning: Could not create prompt session with history: {e}",
                file=sys.stderr,
            )

            # Check if this is expected (non-terminal environment)
            if "not a terminal" in str(e).lower() or "stdin" in str(e).lower():
                print(
                    "This is expected in non-terminal environments (like automated tests)",
                    file=sys.stderr,
                )
                print(
                    "Falling back to basic input mode (history will not be saved)",
                    file=sys.stderr,
                )
            else:
                print("Unexpected error during session creation:", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                print(
                    "Falling back to basic input mode (history will not be saved)",
                    file=sys.stderr,
                )

            return None

    def _process_input(self, user_input: str) -> bool:
        """Process user input."""
        try:
            # Strip whitespace from input
            user_input = user_input.strip()

            # Handle empty input gracefully
            if not user_input:
                return True

            # Check for built-in commands
            if user_input in self.BUILTIN_COMMANDS:
                method_name = self.BUILTIN_COMMANDS[user_input]
                method = getattr(self, method_name)
                # Call command method directly - let exceptions bubble up for testing
                return method()

            # If not a built-in command, treat as IFC query
            self._execute_query(user_input)
            return True

        except Exception as e:
            # For non-command input, handle errors gracefully
            if user_input.strip() not in self.BUILTIN_COMMANDS:
                print(
                    f"ERROR: Unexpected error processing input: '{user_input}'",
                    file=sys.stderr,
                )
                print(f"Error type: {type(e).__name__}", file=sys.stderr)
                print(f"Error message: {e}", file=sys.stderr)
                print("\nFull traceback:", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                print(
                    "\nShell will continue - please try again or type /help for assistance.",
                    file=sys.stderr,
                )
                return True  # Continue shell even after processing errors
            else:
                # Re-raise command method exceptions for testing compatibility
                raise

    def _execute_query(self, query: str) -> None:
        """Execute IFC selector query with comprehensive error handling and debugging.

        CRITICAL: Query results go to STDOUT, all messages go to STDERR.
        """
        try:
            print(f"DEBUG: Executing query: '{query}'", file=sys.stderr)
            print(
                f"DEBUG: Model schema: {getattr(self.model, 'schema', 'Unknown')}",
                file=sys.stderr,
            )

            # Use ifcopenshell.util.selector to filter elements
            results = ifcopenshell.util.selector.filter_elements(self.model, query)

            print(f"DEBUG: Query returned {len(results)} results", file=sys.stderr)

            # Display results - one entity per line in SPF format TO STDOUT
            for i, entity in enumerate(results):
                try:
                    # Convert entity to SPF format (Step Physical File format)
                    spf_line = str(entity)
                    print(spf_line)  # STDOUT for results
                except Exception as entity_error:
                    print(
                        f"ERROR: Failed to convert entity {i} to string format",
                        file=sys.stderr,
                    )
                    print(
                        f"Entity error: {type(entity_error).__name__}: {entity_error}",
                        file=sys.stderr,
                    )
                    print(f"Entity type: {type(entity)}", file=sys.stderr)
                    print("Continuing with next entity...", file=sys.stderr)

            # Empty results produce no additional output (silent)

        except Exception as e:
            # Error reporting with full debugging information TO STDERR
            print("=" * 60, file=sys.stderr)
            print("IFC QUERY EXECUTION ERROR", file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            print(f"Query: {query}", file=sys.stderr)
            print(f"Exception: {type(e).__name__}: {str(e)}", file=sys.stderr)
            print(file=sys.stderr)
            print("FULL PYTHON TRACEBACK:", file=sys.stderr)
            print("-" * 40, file=sys.stderr)

            # Print the traceback to stderr
            traceback.print_exc(file=sys.stderr)

            print("-" * 40, file=sys.stderr)
            print(file=sys.stderr)
            print("DEBUGGING SUGGESTIONS:", file=sys.stderr)

            error_str = str(e).lower()
            if "syntax" in error_str or "parse" in error_str:
                print(
                    "• Check query syntax - ensure it follows IfcOpenShell selector format",
                    file=sys.stderr,
                )
                print(
                    "• Example valid queries: 'IfcWall', 'IfcWall, material=concrete'",
                    file=sys.stderr,
                )
                print(
                    "• See IfcOpenShell documentation for selector syntax details",
                    file=sys.stderr,
                )
            elif "attribute" in error_str:
                print("• Invalid attribute name in query", file=sys.stderr)
                print(
                    "• Check IFC schema documentation for valid attribute names",
                    file=sys.stderr,
                )
                print(
                    "• Ensure attribute names match the IFC specification",
                    file=sys.stderr,
                )
            elif "type" in error_str and "ifc" in error_str.lower():
                print("• Invalid IFC entity type in query", file=sys.stderr)
                print(
                    "• Check that entity type exists in the current model schema",
                    file=sys.stderr,
                )
                print(
                    f"• Model schema: {getattr(self.model, 'schema', 'Unknown')}",
                    file=sys.stderr,
                )
            elif "memory" in error_str:
                print(
                    "• Query result set may be too large for available memory",
                    file=sys.stderr,
                )
                print(
                    "• Try narrowing the query with additional filters", file=sys.stderr
                )
                print(
                    "• Consider using more specific entity types or attribute filters",
                    file=sys.stderr,
                )
            else:
                print(
                    "• Check query syntax and try simpler queries first",
                    file=sys.stderr,
                )
                print(
                    "• Verify the IFC model contains the requested entity types",
                    file=sys.stderr,
                )
                print(
                    "• Try basic queries like 'IfcWall' or 'IfcDoor' to test functionality",
                    file=sys.stderr,
                )

            print(file=sys.stderr)
            print("Query execution failed - shell will continue.", file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            print(file=sys.stderr)  # Add blank line for readability

    def _show_help(self) -> bool:
        """Display help information with error handling."""
        try:
            help_text = """
IfcPeek - Interactive IFC Model Query Tool

USAGE:
  Enter IfcOpenShell selector syntax queries to find matching entities.
  Results are displayed one entity per line in SPF (Step Physical File) format.
  
EXAMPLES:
  IfcWall                           - All walls
  IfcWall, material=concrete        - Concrete walls  
  IfcElement, Name=Door-01          - Element named Door-01
  IfcBuildingElement, type=wall     - Building elements of type wall
  IfcWall | IfcDoor                 - All walls or doors
  
COMMANDS:
  /help    - Show this help
  /exit    - Exit shell
  /quit    - Exit shell
  Ctrl-D   - Exit shell
  Ctrl-C   - Interrupt current operation (return to prompt)
  
HISTORY:
  Up/Down  - Navigate command history (persistent across sessions)
  Ctrl-R   - Search command history
  
QUERY RESULTS:
  - Empty queries produce no output
  - Each matching entity is displayed on a separate line
  - Entities are shown in SPF format (e.g., #123=IFCWALL('guid',...);)
  - Query errors display full traceback for debugging
  
ERROR HANDLING & DEBUGGING:
  - All errors show full Python tracebacks for debugging
  - File loading errors include detailed diagnostic information
  - Query errors provide syntax suggestions and model information
  - Signal handling ensures graceful operation (Ctrl-C returns to prompt)
  
HISTORY FEATURES:
  - Command history is automatically saved between sessions
  - History includes both queries and commands
  - Use Up/Down arrows to navigate previous commands
  - Use Ctrl-R to search through command history
  - History is stored in XDG-compliant location
  
TROUBLESHOOTING:
  - If queries fail, check the full traceback for specific error details
  - For file loading issues, verify file permissions and integrity
  - Use simple queries (IfcWall, IfcDoor) to test basic functionality
  - Signal handling prevents accidental shell termination
  
For selector syntax details, see IfcOpenShell documentation.
Error handling provides full debugging information.
"""
            print(help_text, file=sys.stderr)  # Help goes to STDERR
            return True

        except Exception as e:
            print(f"ERROR: Failed to display help information", file=sys.stderr)
            print(f"Error type: {type(e).__name__}: {e}", file=sys.stderr)
            print("Full traceback:", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            print(
                "Basic help: Type queries like 'IfcWall' or use /exit to quit",
                file=sys.stderr,
            )
            return True

    def _exit(self) -> bool:
        """Handle exit command with cleanup."""
        try:
            print("Exiting IfcPeek...", file=sys.stderr)
            return False
        except Exception as e:
            print(f"ERROR during exit: {type(e).__name__}: {e}", file=sys.stderr)
            print("Force exiting...", file=sys.stderr)
            return False

    def run(self) -> None:
        """Main shell loop with error handling and signal support."""
        try:
            print(f"IfcPeek starting with: {self.ifc_file_path.name}", file=sys.stderr)
            print(
                f"Model schema: {getattr(self.model, 'schema', 'Unknown')}",
                file=sys.stderr,
            )

            # Count entities for user feedback with error handling
            try:
                entity_count = len(self.model.by_type("IfcRoot"))
                print(f"Model contains {entity_count} entities", file=sys.stderr)
            except Exception as count_error:
                print(
                    f"Model entity count unavailable: {type(count_error).__name__}: {count_error}",
                    file=sys.stderr,
                )

            # Show session status with information
            if self.session is not None:
                print(
                    "Interactive shell started with persistent command history.",
                    file=sys.stderr,
                )
                print(
                    "Use Up/Down arrows to navigate history, Ctrl-R to search.",
                    file=sys.stderr,
                )
            else:
                print(
                    "Interactive shell started (basic input mode - no history saved).",
                    file=sys.stderr,
                )

            print(
                "Error handling active - full tracebacks available for debugging.",
                file=sys.stderr,
            )
            print(
                "Signal handling configured - Ctrl-C returns to prompt, Ctrl-D exits.",
                file=sys.stderr,
            )
            print("Type /help for usage information, Ctrl-D to exit.", file=sys.stderr)
            print(file=sys.stderr)

            # Main shell loop with comprehensive error handling
            while True:
                try:
                    if self.session:
                        # Use prompt_toolkit session with history
                        user_input = self.session.prompt("> ")
                    else:
                        # Fallback to basic input
                        user_input = input("> ")

                    # Process the input and check if we should continue
                    should_continue = self._process_input(user_input)

                    if not should_continue:
                        break

                except EOFError:
                    # Handle Ctrl-D gracefully
                    print("\nGoodbye!", file=sys.stderr)
                    break

                except KeyboardInterrupt:
                    # Handle Ctrl-C gracefully - this should be handled by signal handler
                    # but provide fallback behavior
                    print("\n(Use Ctrl-D to exit)", file=sys.stderr)
                    continue

                except Exception as e:
                    # Handle any other unexpected errors in the main loop
                    print(f"Error: {e}", file=sys.stderr)
                    continue

        except Exception as e:
            print(f"CRITICAL ERROR: Shell run loop failed", file=sys.stderr)
            print(f"Error type: {type(e).__name__}", file=sys.stderr)
            print(f"Error message: {e}", file=sys.stderr)
            print("\nFull traceback:", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            print("\nShell cannot continue. Exiting...", file=sys.stderr)
            return

        print("Shell session ended.", file=sys.stderr)

        # Optional: Display history info on exit with error handling
        try:
            if self.session is not None and hasattr(
                self.session.history, "get_strings"
            ):
                history_count = len(list(self.session.history.get_strings()))
                if history_count > 0:
                    print(
                        f"Command history saved ({history_count} entries).",
                        file=sys.stderr,
                    )
        except Exception as history_error:
            print(
                f"Note: Could not display history information: {type(history_error).__name__}: {history_error}",
                file=sys.stderr,
            )
