"""Fixed value extraction functionality for IfcPeek - addresses formatting function parsing issues."""

import sys
import re
import ifcopenshell.util.selector
from .debug import debug_print, error_print, is_debug_enabled


class ValueExtractor:
    """Handles value extraction and formatting for IFC elements."""

    def extract_element_value(self, element, value_query: str) -> str:
        """Extract a single value from an element using IfcOpenShell selector syntax with formatting support.

        Args:
            element: IFC element to extract value from
            value_query: Value extraction query (e.g., 'Name', 'type.Name', 'upper(Name)')

        Returns:
            Extracted value as string, or empty string if extraction fails
        """
        try:
            debug_print(
                f"Extracting '{value_query}' from element #{getattr(element, 'id', lambda: 'Unknown')()}"
            )

            # Check if this is a formatting query (contains function calls)
            if self.is_formatting_query(value_query):
                debug_print(f"Detected as formatting query: {value_query}")
                return self.extract_formatted_value(element, value_query)
            else:
                debug_print(f"Detected as raw value query: {value_query}")
                return self.extract_raw_value(element, value_query)

        except Exception as e:
            # Log detailed error to STDERR but return empty string
            element_id = getattr(element, "id", lambda: "Unknown")()
            print(
                f"Property '{value_query}' not found on entity #{element_id}",
                file=sys.stderr,
            )
            debug_print(
                f"Failed to extract '{value_query}' from element #{element_id}: {type(e).__name__}: {e}"
            )
            return ""

    def extract_raw_value(self, element, value_query: str) -> str:
        """Extract raw value using get_element_value (existing logic).

        Args:
            element: IFC element to extract value from
            value_query: Raw value query (no formatting)

        Returns:
            Extracted value as string
        """
        debug_print(f"Extracting raw value for: {value_query}")

        # Use IfcOpenShell's get_element_value function
        value = ifcopenshell.util.selector.get_element_value(element, value_query)

        debug_print(f"Raw value result: {value} (type: {type(value)})")

        # Handle different value types
        if value is None:
            return ""
        elif isinstance(value, (list, tuple)):
            # Handle lists/tuples with placeholder format
            return f"<List[{len(value)}]>"
        elif hasattr(value, "__dict__") and not isinstance(
            value, (str, int, float, bool)
        ):
            # Handle complex objects with string representation or placeholder
            try:
                str_repr = str(value)
                # If string representation is too long or complex, use placeholder
                if len(str_repr) > 100 or "\n" in str_repr:
                    return f"<Object[{type(value).__name__}]>"
                return str_repr
            except Exception:
                return f"<Object[{type(value).__name__}]>"
        else:
            # Convert to string representation
            return str(value)

    def extract_formatted_value(self, element, format_query: str) -> str:
        """Extract and format value using IfcOpenShell's formatting system.

        Args:
            element: IFC element to extract value from
            format_query: Formatting query (e.g., 'upper(Name)', 'round(type.Width, 0.1)')

        Returns:
            Formatted value as string
        """
        try:
            debug_print(f"Processing formatting query: {format_query}")

            # Step 1: Parse the formatting query to find all value queries and build format string
            processed_format_string = self.build_format_string_fixed(
                element, format_query
            )

            if not processed_format_string:
                debug_print(
                    "No format string could be built - falling back to raw extraction"
                )
                fallback_query = self.extract_first_value_query(format_query)
                if fallback_query:
                    debug_print(f"Trying fallback query: {fallback_query}")
                    return self.extract_raw_value(element, fallback_query)
                debug_print("No fallback query found either")
                return ""

            debug_print(f"Built format string: {processed_format_string}")

            # Step 2: Apply formatting using IfcOpenShell's format function
            formatted_value = ifcopenshell.util.selector.format(processed_format_string)

            debug_print(f"Formatted result: {formatted_value}")

            return str(formatted_value)

        except Exception as e:
            debug_print(
                f"Formatting failed for '{format_query}': {type(e).__name__}: {e}"
            )
            if is_debug_enabled():
                import traceback

                traceback.print_exc(file=sys.stderr)

            # Fallback: try to extract just the first value query we can find
            try:
                fallback_query = self.extract_first_value_query(format_query)
                if fallback_query:
                    debug_print(
                        f"Falling back to raw value extraction: {fallback_query}"
                    )
                    return self.extract_raw_value(element, fallback_query)
            except Exception as fallback_error:
                debug_print(f"Fallback also failed: {fallback_error}")

            return ""

    def build_format_string_fixed(self, element, format_query: str) -> str:
        """FIXED: Build a complete format string by replacing value queries with actual values.

        This version properly handles nested function calls and complex paths.

        Args:
            element: IFC element to extract values from
            format_query: Original formatting query

        Returns:
            Format string with all value queries replaced by quoted actual values
        """
        debug_print(f"Building FIXED format string for: {format_query}")

        # Process the query recursively to handle nested function calls
        result = self.process_nested_functions(element, format_query)

        debug_print(f"Final format string: {result}")
        return result

    def process_nested_functions(self, element, query: str) -> str:
        """Recursively process nested function calls from innermost to outermost.

        Args:
            element: IFC element to extract values from
            query: Query string that may contain nested functions

        Returns:
            Processed query string
        """
        debug_print(f"Processing nested functions in: {query}")

        # Find all quoted strings to avoid replacing content within them
        quoted_strings = []
        quote_pattern = r'"[^"]*"'
        for match in re.finditer(quote_pattern, query):
            quoted_strings.append((match.start(), match.end()))

        def is_inside_quoted_string(pos):
            """Check if a position is inside a quoted string."""
            for start, end in quoted_strings:
                if start <= pos < end:
                    return True
            return False

        known_functions = {
            "upper",
            "lower",
            "title",
            "concat",
            "round",
            "int",
            "number",
            "metric_length",
            "imperial_length",
        }

        # Find the innermost function calls (those without nested function calls inside them)
        function_pattern = r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\("

        # Keep processing until no more function calls are found
        max_iterations = 10  # Prevent infinite loops
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            debug_print(f"Iteration {iteration}: {query}")

            # Find all function calls in current state
            function_matches = []
            for match in re.finditer(function_pattern, query):
                func_name = match.group(1)
                if func_name in known_functions:
                    func_start = match.start()
                    if not is_inside_quoted_string(func_start):
                        # Find the matching closing parenthesis
                        paren_start = match.end() - 1
                        paren_end = self.find_matching_paren(
                            query, paren_start, is_inside_quoted_string
                        )

                        if paren_end != -1:
                            function_matches.append(
                                (func_start, paren_end + 1, func_name, paren_start)
                            )

            if not function_matches:
                debug_print("No more function calls found")
                break

            debug_print(
                f"Found function calls: {[(name, start, end) for start, end, name, _ in function_matches]}"
            )

            # Find innermost functions (those that don't contain other function calls)
            innermost_functions = []
            for func_start, func_end, func_name, paren_start in function_matches:
                args_content = query[paren_start + 1 : func_end - 1]

                # Check if this function's arguments contain other function calls
                has_nested_functions = False
                for other_start, other_end, _, _ in function_matches:
                    if other_start > paren_start and other_end < func_end:
                        has_nested_functions = True
                        break

                if not has_nested_functions:
                    innermost_functions.append(
                        (func_start, func_end, func_name, args_content)
                    )

            if not innermost_functions:
                debug_print("No innermost functions found - stopping")
                break

            debug_print(
                f"Processing innermost functions: {[(name, args) for _, _, name, args in innermost_functions]}"
            )

            # Process innermost functions in reverse order (right to left) to maintain indices
            innermost_functions.sort(key=lambda x: x[0], reverse=True)

            for func_start, func_end, func_name, args_content in innermost_functions:
                debug_print(f"Processing {func_name} with args: '{args_content}'")

                # Process the arguments
                processed_args = self.parse_and_replace_function_arguments(
                    element, args_content
                )

                if processed_args is not None:
                    # Replace the function call with the processed version
                    new_function_call = f"{func_name}({processed_args})"
                    query = query[:func_start] + new_function_call + query[func_end:]
                    debug_print(f"Replaced with: {new_function_call}")
                else:
                    debug_print(f"Failed to process arguments for {func_name}")
                    # Replace with empty string as fallback
                    query = query[:func_start] + '""' + query[func_end:]

        return query

    def find_matching_paren(
        self, text: str, start_pos: int, is_inside_quoted_string
    ) -> int:
        """Find the matching closing parenthesis for an opening parenthesis.

        Args:
            text: The text to search in
            start_pos: Position of the opening parenthesis
            is_inside_quoted_string: Function to check if position is in quoted string

        Returns:
            Position of matching closing parenthesis, or -1 if not found
        """
        if start_pos >= len(text) or text[start_pos] != "(":
            return -1

        open_count = 1
        pos = start_pos + 1

        while pos < len(text) and open_count > 0:
            if not is_inside_quoted_string(pos):
                if text[pos] == "(":
                    open_count += 1
                elif text[pos] == ")":
                    open_count -= 1
            pos += 1

        return pos - 1 if open_count == 0 else -1

    def parse_and_replace_function_arguments(self, element, args_content: str) -> str:
        """Parse function arguments and replace value queries with actual values.

        Args:
            element: IFC element to extract values from
            args_content: The content between function parentheses

        Returns:
            Processed arguments string with value queries replaced, or None if failed
        """
        debug_print(f"Parsing function arguments: '{args_content}'")

        if not args_content.strip():
            return ""

        # Split arguments by comma, but be careful about commas inside quoted strings and nested functions
        args = self.split_function_arguments(args_content)
        debug_print(f"Split into arguments: {args}")

        processed_args = []

        for i, arg in enumerate(args):
            arg = arg.strip()
            debug_print(f"Processing argument {i}: '{arg}'")

            # Check if this argument is already quoted (literal string)
            if arg.startswith('"') and arg.endswith('"'):
                debug_print(f"Argument {i} is already quoted - keeping as is")
                processed_args.append(arg)
            # Check if this argument is a number
            elif self.is_number(arg):
                debug_print(f"Argument {i} is a number - keeping as is")
                processed_args.append(arg)
            # Check if this argument contains a function call (already processed)
            elif any(
                func in arg
                for func in [
                    "upper(",
                    "lower(",
                    "title(",
                    "concat(",
                    "round(",
                    "int(",
                    "number(",
                    "metric_length(",
                    "imperial_length(",
                ]
            ):
                debug_print(f"Argument {i} contains function call - keeping as is")
                processed_args.append(arg)
            else:
                # This should be a value query - extract the value and quote it
                debug_print(f"Argument {i} appears to be a value query")
                try:
                    value = self.extract_raw_value(element, arg)
                    # Handle the case where value extraction returns empty string
                    if value == "":
                        debug_print(
                            f"Value extraction returned empty string for '{arg}' - this might be expected"
                        )
                    quoted_value = f'"{value}"'
                    processed_args.append(quoted_value)
                    debug_print(f"Replaced argument {i} '{arg}' with {quoted_value}")
                except Exception as e:
                    debug_print(
                        f"Failed to extract value for argument {i} '{arg}': {e}"
                    )
                    # Use empty string as fallback
                    processed_args.append('""')

        result = ", ".join(processed_args)
        debug_print(f"Final processed arguments: {result}")
        return result

    def split_function_arguments(self, args_content: str) -> list:
        """Split function arguments by comma, respecting quoted strings and nested parentheses.

        Args:
            args_content: The argument string to split

        Returns:
            List of argument strings
        """
        if not args_content.strip():
            return []

        args = []
        current_arg = ""
        in_quotes = False
        paren_depth = 0
        i = 0

        while i < len(args_content):
            char = args_content[i]

            if char == '"' and (i == 0 or args_content[i - 1] != "\\"):
                in_quotes = not in_quotes
                current_arg += char
            elif not in_quotes:
                if char == "(":
                    paren_depth += 1
                    current_arg += char
                elif char == ")":
                    paren_depth -= 1
                    current_arg += char
                elif char == "," and paren_depth == 0:
                    # This comma is at the top level - it's an argument separator
                    args.append(current_arg.strip())
                    current_arg = ""
                else:
                    current_arg += char
            else:
                current_arg += char

            i += 1

        # Don't forget the last argument
        if current_arg.strip():
            args.append(current_arg.strip())

        return args

    def is_number(self, text: str) -> bool:
        """Check if a string represents a number.

        Args:
            text: String to check

        Returns:
            True if the string is a number
        """
        try:
            float(text)
            return True
        except ValueError:
            return False

    def is_formatting_query(self, value_query: str) -> bool:
        """Check if a value query contains formatting functions.

        Args:
            value_query: The query string to check

        Returns:
            True if the query contains formatting functions, False otherwise
        """
        debug_print(f"Checking if '{value_query}' is a formatting query")

        # Known formatting functions from the documentation
        formatting_functions = [
            "upper",
            "lower",
            "title",
            "concat",
            "round",
            "int",
            "number",
            "metric_length",
            "imperial_length",
        ]

        # Check for function patterns: function_name(...)
        for func in formatting_functions:
            pattern = rf"\b{re.escape(func)}\s*\("
            if re.search(pattern, value_query):
                debug_print(f"Found formatting function '{func}' in query")
                return True

        debug_print("No formatting functions found in query")
        return False

    def extract_first_value_query(self, format_query: str) -> str:
        """Extract the first value query from a formatting query for fallback purposes.

        Args:
            format_query: Formatting query string

        Returns:
            First value query found, or empty string if none found
        """
        debug_print(f"Extracting first value query from: {format_query}")

        # Look for patterns that could be value queries
        # Priority order: complex paths first, then simple ones
        patterns = [
            # Complex paths with dots and indices (like ObjectPlacement.RelativePlacement.Location.Coordinates.0)
            r"\b[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*\.\d+\b",
            # Property set patterns
            r"\bPset_[a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*\b",
            # Regular paths with dots
            r"\b[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)+\b",
            # Simple property names
            r"\b(?:Name|class|id|predefined_type|x|y|z|easting|northing|elevation)\b",
        ]

        known_functions = {
            "upper",
            "lower",
            "title",
            "concat",
            "round",
            "int",
            "number",
            "metric_length",
            "imperial_length",
        }

        for pattern in patterns:
            matches = re.findall(pattern, format_query)
            for match in matches:
                if match not in known_functions:
                    debug_print(f"Found first value query: {match}")
                    return match

        debug_print("No value query found in format string")
        return ""

    def process_value_queries(self, elements: list, value_queries: list) -> list:
        """Process value queries for a list of elements.

        Args:
            elements: List of IFC elements to extract values from
            value_queries: List of value extraction queries

        Returns:
            List of lists: [element][value_query] containing extracted values
        """
        try:
            debug_print(
                f"Processing {len(value_queries)} value queries for {len(elements)} elements"
            )

            results = []

            for element in elements:
                element_values = []
                element_id = getattr(element, "id", lambda: "Unknown")()

                debug_print(f"Processing element #{element_id}")

                for value_query in value_queries:
                    try:
                        value = self.extract_element_value(element, value_query)
                        element_values.append(value)
                    except Exception as e:
                        # This should not happen since extract_element_value handles exceptions,
                        # but provide extra safety
                        error_print(
                            f"Unexpected error extracting '{value_query}' from element #{element_id}: {e}"
                        )
                        element_values.append("")

                results.append(element_values)

            debug_print(f"Completed processing {len(results)} element results")
            return results

        except Exception as e:
            # Handle any unexpected errors in batch processing
            error_print(f"Failed to process value queries: {e}")
            debug_print(f"Error type: {type(e).__name__}: {e}")
            if is_debug_enabled():
                import traceback

                traceback.print_exc(file=sys.stderr)

            # Return empty results to prevent further errors
            return []

    def format_value_output(self, values: list) -> str:
        """Format extracted values for output.

        Args:
            values: List of extracted values for a single entity

        Returns:
            Formatted output string according to CSV/tab-separated specifications
        """
        try:
            if not values:
                return ""
            elif len(values) == 1:
                # Single value - output value only (no tabs)
                return str(values[0]) if values[0] is not None else ""
            else:
                # Multiple values - tab-separated
                # Ensure no tabs in individual values (replace with spaces)
                clean_values = []
                for value in values:
                    if value is None:
                        clean_values.append("")
                    else:
                        # Convert to string and replace tabs with spaces
                        clean_value = str(value).replace("\t", " ")
                        clean_values.append(clean_value)
                return "\t".join(clean_values)

        except Exception as e:
            error_print(f"Failed to format values {values}: {e}")
            if is_debug_enabled():
                import traceback

                traceback.print_exc(file=sys.stderr)
            return ""
