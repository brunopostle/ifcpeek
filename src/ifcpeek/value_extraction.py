"""Value extraction functionality for IfcPeek."""

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
            processed_format_string = self.build_format_string(element, format_query)

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
                import sys

                debug_print("Full formatting traceback:")
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

    def build_format_string(self, element, format_query: str) -> str:
        """Build a complete format string by replacing value queries with actual values.

        Args:
            element: IFC element to extract values from
            format_query: Original formatting query

        Returns:
            Format string with all value queries replaced by quoted actual values
        """
        import re

        debug_print(f"Building format string for: {format_query}")

        # First, find all quoted strings to avoid replacing content within them
        quoted_strings = []
        quote_pattern = r'"[^"]*"'
        for match in re.finditer(quote_pattern, format_query):
            quoted_strings.append((match.start(), match.end()))

        debug_print(f"Found quoted string regions: {quoted_strings}")

        # Enhanced regex patterns ordered by specificity (most specific first)
        # This prevents overlapping matches
        patterns = [
            # Property set patterns with dots (most specific)
            r"\bPset_[a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*\b",
            # Regex property patterns (between forward slashes)
            r"/[^/]+/\.[a-zA-Z_][a-zA-Z0-9_]*",
            # Property paths (word.word or word.word.word, etc.) - before single words
            r"\b[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)+\b",
            # Common single properties (including coordinates) - after paths to avoid conflicts
            r"\b(?:Name|class|id|predefined_type|x|y|z|easting|northing|elevation|description)\b",
        ]

        # Known formatting functions to exclude from replacement
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

        def is_inside_quoted_string(pos):
            """Check if a position is inside a quoted string."""
            for start, end in quoted_strings:
                if start <= pos < end:
                    return True
            return False

        def is_overlapping(new_start, new_end, existing_matches):
            """Check if a new match overlaps with any existing matches."""
            for start, end, _ in existing_matches:
                if not (new_end <= start or new_start >= end):
                    return True
            return False

        # Find all potential value queries, excluding those inside quoted strings
        # Process patterns in order of specificity to avoid overlaps
        all_matches = []

        for pattern in patterns:
            matches = re.finditer(pattern, format_query)
            for match in matches:
                potential_query = match.group(0)
                start_pos = match.start()
                end_pos = match.end()

                # Skip if this is a known function name
                if potential_query in known_functions:
                    debug_print(f"Skipping function name: {potential_query}")
                    continue

                # Skip if this match is inside a quoted string
                if is_inside_quoted_string(start_pos):
                    debug_print(f"Skipping '{potential_query}' - inside quoted string")
                    continue

                # Skip if this match overlaps with an existing match
                if is_overlapping(start_pos, end_pos, all_matches):
                    debug_print(
                        f"Skipping '{potential_query}' - overlaps with existing match"
                    )
                    continue

                all_matches.append((start_pos, end_pos, potential_query))
                debug_print(
                    f"Added non-overlapping match: '{potential_query}' at {start_pos}-{end_pos}"
                )

        # Sort by start position in reverse order for safe replacement
        all_matches.sort(key=lambda x: x[0], reverse=True)

        debug_print(
            f"Final non-overlapping value queries: {[q for _, _, q in all_matches]}"
        )

        # Process matches and build replacement list
        result = format_query
        successful_replacements = 0

        for start, end, potential_query in all_matches:
            debug_print(
                f"Attempting to extract value for: '{potential_query}' at position {start}-{end}"
            )

            # Try to extract the value
            try:
                value = self.extract_raw_value(element, potential_query)
                debug_print(f"Extracted value for '{potential_query}': '{value}'")

                # Replace even if value is empty (to handle null/empty cases properly)
                # Quote the value properly for the format function
                quoted_value = f'"{value}"'

                # Verify we're replacing the right text
                original_text = result[start:end]
                if original_text != potential_query:
                    debug_print(
                        f"WARNING: Text mismatch. Expected '{potential_query}', found '{original_text}'"
                    )
                    continue

                result = result[:start] + quoted_value + result[end:]
                debug_print(f"Replaced '{potential_query}' with {quoted_value}")
                successful_replacements += 1

            except Exception as e:
                debug_print(
                    f"Could not extract value for '{potential_query}': {type(e).__name__}: {e}"
                )
                # For failed extractions, replace with empty string
                quoted_value = '""'
                result = result[:start] + quoted_value + result[end:]
                debug_print(f"Replaced failed '{potential_query}' with empty string")
                successful_replacements += 1

        debug_print(f"Made {successful_replacements} successful replacements")
        debug_print(f"Final format string: {result}")

        return result

    def extract_first_value_query(self, format_query: str) -> str:
        """Extract the first value query from a formatting query for fallback purposes.

        Args:
            format_query: Formatting query string

        Returns:
            First value query found, or empty string if none found
        """
        import re

        debug_print(f"Extracting first value query from: {format_query}")

        # Use the same patterns as in build_format_string
        patterns = [
            r"\b[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)+\b",
            r"\bPset_[a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*\b",
            r"/[^/]+/\.[a-zA-Z_][a-zA-Z0-9_]*",
            r"\b(?:Name|class|id|predefined_type|x|y|z|easting|northing|elevation)\b",
            r"\b(?:material|storey|building|site|container|space|parent|type|types|occurrences|description)\b",
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

    def is_formatting_query(self, value_query: str) -> bool:
        """Check if a value query contains formatting functions.

        Args:
            value_query: The query string to check

        Returns:
            True if the query contains formatting functions, False otherwise
        """
        import re

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
        # This regex looks for word boundaries, function name, optional whitespace, then opening parenthesis
        for func in formatting_functions:
            pattern = rf"\b{re.escape(func)}\s*\("
            if re.search(pattern, value_query):
                debug_print(f"Found formatting function '{func}' in query")
                return True

        debug_print("No formatting functions found in query")
        return False

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
                import sys

                print("Full traceback:", file=sys.stderr)
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
                import sys

                traceback.print_exc(file=sys.stderr)
            return ""

    def parse_formatting_query(self, format_query: str) -> str:
        """Parse a formatting query to extract the inner value query.

        This method is kept for backwards compatibility but enhanced to handle multiple value queries.

        Args:
            format_query: Formatting query (e.g., 'upper(type.Name)')

        Returns:
            First inner value query (e.g., 'type.Name')
        """
        return self.extract_first_value_query(format_query)


# Add missing import for sys
import sys
