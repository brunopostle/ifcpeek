"""
Updated shell.py with enhanced tab completion for both filter queries and value extraction.
Replace the existing shell.py with this enhanced version.
"""

import sys
import signal
import traceback
import ifcopenshell
import ifcopenshell.util.selector
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

from .config import validate_ifc_file_path, get_history_file_path
from .exceptions import InvalidIfcFileError
from .formatters import format_query_results
from .value_extraction import ValueExtractor
from .debug import (
    debug_print,
    verbose_print,
    error_print,
    warning_print,
    is_debug_enabled,
)


class IfcPeek:
    """Interactive IFC query shell with enhanced tab completion for both filter and value queries."""

    BUILTIN_COMMANDS = {
        "/help": "_show_help",
        "/exit": "_exit",
        "/quit": "_exit",
        "/debug": "_toggle_debug",
        "/completion": "_show_completion_debug",
        "/test": "_test_completion",
    }

    def __init__(
        self, ifc_file_path: str, force_session_creation: bool = False
    ) -> None:
        """Initialize shell with IFC model, enhanced tab completion, and error handling."""
        verbose_print(f"IfcPeek initializing with file: {ifc_file_path}")

        self.force_session_creation = force_session_creation
        self.value_extractor = ValueExtractor()

        # Validate and load IFC file
        try:
            validated_path = validate_ifc_file_path(ifc_file_path)
            self.ifc_file_path = validated_path.resolve()
            debug_print(f"File validated: {self.ifc_file_path}")
        except Exception as e:
            error_print(f"File validation failed for '{ifc_file_path}'")
            error_print(f"Error details: {type(e).__name__}: {e}")
            if is_debug_enabled():
                traceback.print_exc(file=sys.stderr)
            raise

        try:
            self.model = self._load_model()
            verbose_print("IFC model loaded successfully")
        except Exception:
            error_print("Failed to load IFC model")
            if is_debug_enabled():
                traceback.print_exc(file=sys.stderr)
            raise

        # Build enhanced completion system
        try:
            print("Building enhanced completion system...", file=sys.stderr)
            from .dynamic_completion import create_dynamic_completion_system

            self.completion_cache, self.completer = create_dynamic_completion_system(
                self.model
            )

            # Print summary of what was cached
            debug_info = self.completer.get_debug_info()
            print(
                f"Enhanced completion ready: {debug_info['total_classes']} classes, "
                f"{debug_info['cached_attributes']} classes with attributes, "
                f"{debug_info['property_sets']} property sets",
                file=sys.stderr,
            )

        except Exception as e:
            warning_print(f"Failed to build enhanced completion system: {e}")
            if is_debug_enabled():
                traceback.print_exc(file=sys.stderr)
            self.completion_cache = None
            self.completer = None

        # Create session
        try:
            self.session = self._create_session()
        except Exception as e:
            warning_print(f"Session creation failed: {e}")
            self.session = None

        self._setup_signal_handlers()

    def _load_model(self):
        """Load IFC model."""
        try:
            model = ifcopenshell.open(str(self.ifc_file_path))
            if model is None:
                raise InvalidIfcFileError("Failed to load IFC file")
            return model
        except Exception as e:
            raise InvalidIfcFileError(f"Failed to load IFC file: {e}") from e

    def _create_session(self):
        """Create prompt_toolkit session with enhanced tab completion."""
        try:
            history_path = get_history_file_path()
            file_history = FileHistory(str(history_path))

            session = PromptSession(
                history=file_history,
                completer=self.completer,
                complete_while_typing=False,
                mouse_support=False,
                complete_style="column",
            )

            debug_print("Session created with enhanced tab completion")
            return session

        except Exception as e:
            warning_print(f"Could not create session with history: {e}")
            return None

    def _setup_signal_handlers(self):
        """Setup signal handlers."""
        try:

            def sigint_handler(signum, frame):
                print("\n(Use Ctrl-D to exit, or type /exit)", file=sys.stderr)
                return

            def sigterm_handler(signum, frame):
                print("\nShutting down gracefully...", file=sys.stderr)
                sys.exit(0)

            signal.signal(signal.SIGINT, sigint_handler)
            signal.signal(signal.SIGTERM, sigterm_handler)

        except Exception as e:
            warning_print(f"Could not setup signal handlers: {e}")

    def _parse_combined_query(self, user_input: str) -> tuple:
        """Parse semicolon-separated query."""
        parts = [part.strip() for part in user_input.split(";")]

        if len(parts) == 1:
            return parts[0], [], False

        filter_query = parts[0]
        value_queries = [vq for vq in parts[1:] if vq]

        if not filter_query:
            raise ValueError("Filter query cannot be empty")

        return filter_query, value_queries, True

    def _process_input(self, user_input: str) -> bool:
        """Process user input."""
        user_input = user_input.strip()

        if not user_input:
            return True

        if user_input in self.BUILTIN_COMMANDS:
            method_name = self.BUILTIN_COMMANDS[user_input]
            method = getattr(self, method_name)
            return method()

        try:
            filter_query, value_queries, is_combined = self._parse_combined_query(
                user_input
            )

            if is_combined:
                self._execute_combined_query(filter_query, value_queries)
            else:
                self._execute_query(filter_query)

            return True

        except ValueError as e:
            error_print(f"Query parsing failed: {e}")
            return True
        except Exception as e:
            error_print(f"Unexpected error: {e}")
            if is_debug_enabled():
                traceback.print_exc(file=sys.stderr)
            return True

    def _execute_query(self, query: str) -> None:
        """Execute IFC selector query."""
        try:
            results = ifcopenshell.util.selector.filter_elements(self.model, query)

            for formatted_line in format_query_results(
                results, enable_highlighting=True
            ):
                print(formatted_line)

        except Exception as e:
            print("=" * 60, file=sys.stderr)
            print("IFC QUERY EXECUTION ERROR", file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            print(f"Query: {query}", file=sys.stderr)
            print(f"Exception: {type(e).__name__}: {str(e)}", file=sys.stderr)
            if is_debug_enabled():
                traceback.print_exc(file=sys.stderr)
            print("=" * 60, file=sys.stderr)

    def _execute_combined_query(self, filter_query: str, value_queries: list) -> None:
        """Execute combined filter and value extraction query."""
        try:
            results = ifcopenshell.util.selector.filter_elements(
                self.model, filter_query
            )

            if not results:
                return

            if not value_queries:
                for formatted_line in format_query_results(
                    results, enable_highlighting=True
                ):
                    print(formatted_line)
                return

            element_values_matrix = self.value_extractor.process_value_queries(
                results, value_queries
            )

            for element_values in element_values_matrix:
                if element_values:
                    output_line = self.value_extractor.format_value_output(
                        element_values
                    )
                    print(output_line)

        except Exception as e:
            print("=" * 60, file=sys.stderr)
            print("COMBINED QUERY EXECUTION ERROR", file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            print(f"Filter query: {filter_query}", file=sys.stderr)
            print(f"Value queries: {value_queries}", file=sys.stderr)
            print(f"Exception: {type(e).__name__}: {str(e)}", file=sys.stderr)
            if is_debug_enabled():
                traceback.print_exc(file=sys.stderr)
            print("=" * 60, file=sys.stderr)

    def _show_help(self) -> bool:
        """Display enhanced help information."""
        help_text = """
IfcPeek - Interactive IFC Model Query Tool

USAGE:
  Enter IfcOpenShell selector syntax queries to find matching entities.

BASIC QUERIES with TAB COMPLETION:
  IfcW<TAB>                         - Complete to IfcWall, IfcWindow, etc.
  IfcWall<TAB>                      - Shows: comma, attributes (Name, etc.), keywords (material, etc.)
  IfcWall, <TAB>                    - Shows: IFC classes, attributes, filter keywords
  IfcWall, Name<TAB>                - Shows: comparison operators (=, !=, etc.)
  IfcWall, Pset_<TAB>               - Shows: available property sets
  IfcWall, Pset_WallCommon.<TAB>    - Shows: properties in that property set

EXAMPLE FILTER QUERIES:
  IfcWall                           - All walls
  IfcWall, material=concrete        - Concrete walls  
  IfcElement, Name=Door-01          - Element named Door-01
  IfcWall, Pset_WallCommon.FireRating=2HR - 2-hour fire rated walls

VALUE EXTRACTION with TAB COMPLETION:
  IfcWall ; <TAB>                   - Shows wall-specific attributes + common properties
  IfcWall ; Name                    - Wall names
  IfcWall ; Name ; type.Name        - Wall names and type names
  IfcWall ; type.<TAB>              - Shows type attributes  
  IfcWall ; material.<TAB>          - Shows material attributes (Name, Category, item)
  IfcWall ; Pset_WallCommon.<TAB>   - Shows properties in that property set

SMART TAB COMPLETION FEATURES:
  - Class completion: IfcW<TAB> → IfcWall, IfcWindow, IfcWallStandardCase
  - Context-aware attributes: Different completions for IfcWall vs IfcDoor
  - Property set completion: Pset_<TAB> → actual property sets in your model
  - Filter keyword completion: Shows material, type, location, etc.
  - Value path completion: Analyzes filter query to suggest relevant attributes

FORMATTING FUNCTIONS:
  IfcWall ; upper(Name)             - Wall names in uppercase
  IfcWall ; round(type.Width, 0.1)  - Rounded width values
  IfcWall ; concat(Name, " - ", type.Name) - Combined values

COMMANDS:
  /help       - Show this help
  /exit       - Exit shell  
  /quit       - Exit shell
  /debug      - Toggle debug mode
  /completion - Show completion system debug info
  /test       - Test completion for a specific query
  Ctrl-D      - Exit shell

HISTORY:
  Up/Down  - Navigate command history
  Ctrl-R   - Search command history

For complete selector syntax details, see IfcOpenShell documentation.
"""
        print(help_text, file=sys.stderr)
        return True

    def _exit(self) -> bool:
        """Exit the shell."""
        verbose_print("Exiting IfcPeek...")
        return False

    def _toggle_debug(self) -> bool:
        """Toggle debug mode."""
        from .debug import enable_debug, disable_debug

        if is_debug_enabled():
            disable_debug()
            print("Debug mode disabled.", file=sys.stderr)
        else:
            enable_debug()
            print("Debug mode enabled.", file=sys.stderr)
        return True

    def _show_completion_debug(self) -> bool:
        """Show debug information about the completion system."""
        if not self.completer or not self.completion_cache:
            print("Completion system not available.", file=sys.stderr)
            return True

        debug_info = self.completer.get_debug_info()

        print("=" * 60, file=sys.stderr)
        print("ENHANCED COMPLETION SYSTEM DEBUG INFORMATION", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(
            f"Total IFC classes in model: {debug_info['total_classes']}",
            file=sys.stderr,
        )
        print(
            f"Classes with cached attributes: {debug_info['cached_attributes']}",
            file=sys.stderr,
        )
        print(f"Property sets found: {debug_info['property_sets']}", file=sys.stderr)
        print(f"Selector keywords: {debug_info['selector_keywords']}", file=sys.stderr)
        print(f"Filter keywords: {debug_info['filter_keywords']}", file=sys.stderr)
        print(f"Common attributes: {debug_info['common_attributes']}", file=sys.stderr)

        print("\nSample IFC classes:", file=sys.stderr)
        for cls in debug_info["sample_classes"]:
            attr_count = len(self.completion_cache.attribute_cache.get(cls, set()))
            print(f"  {cls}: {attr_count} attributes", file=sys.stderr)

        print("\nSample property sets:", file=sys.stderr)
        for pset in debug_info["sample_property_sets"]:
            prop_count = len(self.completion_cache.properties_by_pset.get(pset, set()))
            print(f"  {pset}: {prop_count} properties", file=sys.stderr)

        # Show some sample attributes for the first few classes
        print("\nSample attributes for first 3 classes:", file=sys.stderr)
        sample_classes = list(self.completion_cache.ifc_classes_in_model)[:3]
        for cls in sample_classes:
            attrs = self.completion_cache.attribute_cache.get(cls, set())
            sample_attrs = sorted(list(attrs)[:8])  # Show first 8 attributes
            if len(attrs) > 8:
                sample_attrs.append(f"... and {len(attrs) - 8} more")
            print(f"  {cls}: {', '.join(sample_attrs)}", file=sys.stderr)

        print("=" * 60, file=sys.stderr)
        return True

    def _test_completion(self) -> bool:
        """Interactive completion testing command."""
        if not self.completion_cache:
            print("Completion system not available.", file=sys.stderr)
            return True

        print(
            "Enter a partial query to test completions (or empty line to cancel):",
            file=sys.stderr,
        )
        try:
            test_query = input("Test query: ")
            if not test_query.strip():
                print("Test cancelled.", file=sys.stderr)
                return True

            self.test_completion_for_query(test_query.strip())
        except (KeyboardInterrupt, EOFError):
            print("\nTest cancelled.", file=sys.stderr)

        return True

    def test_completion_for_query(self, query: str) -> None:
        """Test what completions would be available for a given query."""
        if not self.completion_cache:
            print("Completion system not available.", file=sys.stderr)
            return

        print(f"\nTesting completions for: '{query}'", file=sys.stderr)
        print("=" * 50, file=sys.stderr)

        # Determine if this is a filter query or value extraction
        if ";" in query:
            # Value extraction context
            parts = query.split(";")
            filter_part = parts[0].strip()
            value_part = parts[-1].strip() if len(parts) > 1 else ""

            print("Context: Value extraction query", file=sys.stderr)
            print(f"Filter part: '{filter_part}'", file=sys.stderr)
            print(f"Value part: '{value_part}'", file=sys.stderr)

            # Extract classes from filter
            relevant_classes = self.completion_cache.extract_ifc_classes_from_query(
                filter_part
            )
            print(
                f"Detected classes: {', '.join(sorted(relevant_classes)) if relevant_classes else 'All classes'}",
                file=sys.stderr,
            )

            # Test value extraction completion
            try:
                from .dynamic_completion import DynamicContextResolver

                resolver = DynamicContextResolver(self.completion_cache)
                completions = resolver.get_completions_for_path(filter_part, value_part)

                print(f"\nAvailable completions ({len(completions)}):", file=sys.stderr)
                sorted_completions = sorted(list(completions))
                for i, completion in enumerate(
                    sorted_completions[:20]
                ):  # Show first 20
                    print(f"  {completion}", file=sys.stderr)
                if len(sorted_completions) > 20:
                    print(
                        f"  ... and {len(sorted_completions) - 20} more",
                        file=sys.stderr,
                    )

            except Exception as e:
                print(f"Error getting value completions: {e}", file=sys.stderr)

        else:
            # Filter query context
            print("Context: Filter query", file=sys.stderr)

            # Extract classes from the query
            relevant_classes = self.completion_cache.extract_ifc_classes_from_query(
                query
            )
            print(
                f"Detected classes: {', '.join(sorted(relevant_classes)) if relevant_classes else 'None detected'}",
                file=sys.stderr,
            )

            # Analyze filter context
            from .enhanced_completion import FilterQueryCompleter

            filter_completer = FilterQueryCompleter(self.completion_cache)
            context = filter_completer._analyze_filter_context(query)

            print("\nFilter context analysis:", file=sys.stderr)
            for key, value in context.items():
                if value and key != "current_pset" and key != "current_attribute":
                    print(f"  {key}: {value}", file=sys.stderr)
                elif key in ("current_pset", "current_attribute") and value:
                    print(f"  {key}: {value}", file=sys.stderr)

            # Get contextual completions
            completions = filter_completer._get_contextual_completions(query, "")

            print(
                f"\nAvailable filter completions ({len(completions)}):", file=sys.stderr
            )
            sorted_completions = sorted(list(completions))
            for i, completion in enumerate(sorted_completions[:20]):  # Show first 20
                print(f"  {completion}", file=sys.stderr)
            if len(sorted_completions) > 20:
                print(f"  ... and {len(sorted_completions) - 20} more", file=sys.stderr)

        print("=" * 50, file=sys.stderr)

    def run(self) -> None:
        """Main shell loop."""
        try:
            verbose_print("IfcPeek starting")
            if self.session and self.completer:
                verbose_print("Enhanced tab completion enabled")
                verbose_print(
                    "- Filter queries: TAB for IFC classes, attributes, keywords"
                )
                verbose_print("- Value extraction: TAB for context-aware properties")
            verbose_print("Type /help for usage information")

            while True:
                try:
                    if self.session:
                        user_input = self.session.prompt("> ")
                    else:
                        user_input = input("> ")

                    if not self._process_input(user_input):
                        break

                except EOFError:
                    print("\nGoodbye!", file=sys.stderr)
                    break
                except KeyboardInterrupt:
                    print("\n(Use Ctrl-D to exit)", file=sys.stderr)
                    continue
                except Exception as e:
                    error_print(f"Unexpected error: {e}")
                    continue

        except Exception:
            error_print("Critical error in shell loop")
            if is_debug_enabled():
                traceback.print_exc(file=sys.stderr)

        verbose_print("Shell session ended")
