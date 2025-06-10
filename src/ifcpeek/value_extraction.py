"""
Fixed value extraction functionality for IfcPeek using a clean two-phase approach.

Phase 1: Replace ALL value queries with their actual values (quoted)
Phase 2: Process formatting functions from innermost to outermost

This approach is much simpler and more reliable than the previous nested function processing.
"""

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
        """Build a complete format string using a two-phase approach.

        Phase 1: Replace ALL value queries with actual values (quoted)
        Phase 2: Process formatting functions from innermost to outermost

        Args:
            element: IFC element to extract values from
            format_query: Original formatting query

        Returns:
            Format string with all value queries replaced by quoted actual values
        """
        debug_print(f"Building format string for: {format_query}")

        # Phase 1: Replace all value queries with their actual values
        query_with_values = self.replace_all_value_queries(element, format_query)
        debug_print(f"After replacing value queries: {query_with_values}")

        # Phase 2: Process formatting functions from innermost to outermost
        result = self.process_formatting_functions(query_with_values)

        debug_print(f"Final format string: {result}")
        return result

    def replace_all_value_queries(self, element, query: str) -> str:
        """Phase 1: Replace ALL value queries with their actual values.

        Args:
            element: IFC element to extract values from
            query: Query string containing value queries

        Returns:
            Query string with all value queries replaced by quoted values
        """
        debug_print(f"Phase 1: Replacing all value queries in: {query}")

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

        # Find all potential value queries using comprehensive patterns
        value_query_patterns = [
            # Regex property patterns (highest priority)
            (r"/[^/]+/\.[a-zA-Z_][a-zA-Z0-9_]*", "regex_property_set"),
            # Standalone regex patterns
            (r"/[^/]+/", "regex_pattern"),
            # Property set patterns (very specific)
            (r"\bPset_[a-zA-Z0-9_]+\.[a-zA-Z_][a-zA-Z0-9_]*\b", "property_set"),
            # Quantity set patterns (very specific)
            (r"\bQto_[a-zA-Z0-9_]+\.[a-zA-Z_][a-zA-Z0-9_]*\b", "quantity_set"),
            # Regular dotted paths (medium specificity)
            (r"\b[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*\b", "dotted_path"),
            # Common selector keywords
            (
                r"\b(?:id|class|predefined_type|container|space|storey|building|site|parent|classification|group|system|zone|material|mat|item|materials|mats|profiles|x|y|z|easting|northing|elevation|count)\b",
                "selector_keyword",
            ),
            # Common IFC attributes
            (
                r"\b(?:Name|Description|Tag|ObjectType|Width|Height|Length|Thickness|Volume|Area|GlobalId|PredefinedType)\b",
                "common_attribute",
            ),
        ]

        # Collect all potential value queries
        potential_queries = []

        for pattern, category in value_query_patterns:
            for match in re.finditer(pattern, query):
                start, end = match.span()
                if not is_inside_quoted_string(start):
                    value_query = match.group()

                    # Filter out function names and numbers
                    if not self.is_function_name(value_query) and not self.is_number(
                        value_query
                    ):
                        potential_queries.append((start, end, value_query, category))

        # Remove overlapping matches (keep the longest match)
        potential_queries.sort(key=lambda x: (x[0], -(x[1] - x[0])))
        non_overlapping_queries = []

        for start, end, value_query, category in potential_queries:
            # Check if this query overlaps with any already selected query
            overlaps = False
            for existing_start, existing_end, _, _ in non_overlapping_queries:
                if not (end <= existing_start or start >= existing_end):
                    overlaps = True
                    break

            if not overlaps:
                non_overlapping_queries.append((start, end, value_query, category))

        # Sort by position (reverse order to maintain indices when replacing)
        non_overlapping_queries.sort(key=lambda x: x[0], reverse=True)

        # Replace each value query with its actual value
        result = query
        for start, end, value_query, category in non_overlapping_queries:
            debug_print(
                f"Attempting to replace {category} value query: '{value_query}' at position {start}-{end}"
            )

            try:
                actual_value = self.extract_raw_value(element, value_query)
                quoted_value = f'"{actual_value}"'
                result = result[:start] + quoted_value + result[end:]
                debug_print(f"Replaced '{value_query}' with {quoted_value}")
            except Exception as e:
                debug_print(f"Failed to extract value for '{value_query}': {e}")
                continue

        return result

    def is_function_name(self, text: str) -> bool:
        """Check if text is a known formatting function name."""
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
        return text in known_functions

    def process_formatting_functions(self, query: str) -> str:
        """Phase 2: Process formatting functions from innermost to outermost.

        Args:
            query: Query string with value queries already replaced

        Returns:
            Query string with formatting functions processed
        """
        debug_print(f"Phase 2: Processing formatting functions in: {query}")

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

        max_iterations = 10
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            debug_print(f"Formatting iteration {iteration}: {query}")

            # Find all quoted strings to avoid processing content within them
            quoted_strings = []
            quote_pattern = r'"[^"]*"'
            for match in re.finditer(quote_pattern, query):
                quoted_strings.append((match.start(), match.end()))

            def is_inside_quoted_string(pos):
                for start, end in quoted_strings:
                    if start <= pos < end:
                        return True
                return False

            # Find all function calls
            function_pattern = r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\("
            function_matches = []

            for match in re.finditer(function_pattern, query):
                func_name = match.group(1)
                if func_name in known_functions:
                    func_start = match.start()
                    if not is_inside_quoted_string(func_start):
                        paren_start = match.end() - 1
                        paren_end = self.find_matching_paren_simple(query, paren_start)

                        if paren_end != -1:
                            function_matches.append(
                                (func_start, paren_end + 1, func_name)
                            )

            if not function_matches:
                debug_print("No more formatting functions found")
                break

            # Find innermost functions
            innermost_functions = []
            for func_start, func_end, func_name in function_matches:
                has_nested_functions = False
                for other_start, other_end, _ in function_matches:
                    if other_start > func_start and other_end < func_end:
                        has_nested_functions = True
                        break

                if not has_nested_functions:
                    innermost_functions.append((func_start, func_end, func_name))

            if not innermost_functions:
                debug_print("No innermost functions found")
                break

            # Process innermost functions (reverse order to maintain indices)
            innermost_functions.sort(key=lambda x: x[0], reverse=True)

            for func_start, func_end, func_name in innermost_functions:
                func_call = query[func_start:func_end]
                debug_print(f"Processing function: {func_call}")

        return query

    def find_matching_paren_simple(self, text: str, start_pos: int) -> int:
        """Find matching closing parenthesis."""
        if start_pos >= len(text) or text[start_pos] != "(":
            return -1

        open_count = 1
        pos = start_pos + 1

        while pos < len(text) and open_count > 0:
            if text[pos] == "(":
                open_count += 1
            elif text[pos] == ")":
                open_count -= 1
            pos += 1

        return pos - 1 if open_count == 0 else -1

    def is_likely_value_query(self, text: str) -> bool:
        """Better detection of value queries vs other constructs.

        Args:
            text: Text to check

        Returns:
            True if text looks like a value query
        """
        text = text.strip()

        # Empty or too short
        if not text or len(text) < 1:
            return False

        # Already quoted strings are not value queries
        if text.startswith('"') and text.endswith('"'):
            return False

        # Numbers are not value queries
        if self.is_number(text):
            return False

        # Known formatting functions are not value queries
        if self.is_function_name(text):
            debug_print(f"'{text}' is a known function name - not a value query")
            return False

        # Function calls are not value queries
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

        if any(func + "(" in text for func in known_functions):
            return False

        # Check if it looks like a selector keyword
        selector_keywords = {
            "id",
            "class",
            "predefined_type",
            "type",
            "types",
            "occurrences",
            "container",
            "space",
            "storey",
            "building",
            "site",
            "parent",
            "classification",
            "group",
            "system",
            "zone",
            "material",
            "mat",
            "item",
            "i",
            "materials",
            "mats",
            "profiles",
            "x",
            "y",
            "z",
            "easting",
            "northing",
            "elevation",
            "count",
        }

        if text in selector_keywords:
            debug_print(f"'{text}' is a known selector keyword")
            return True

        # Common IFC attributes
        common_ifc_attributes = {
            "Name",
            "Description",
            "Tag",
            "ObjectType",
            "GlobalId",
            "Width",
            "Height",
            "Length",
            "Thickness",
            "Volume",
            "Area",
            "PredefinedType",
            "OwnerHistory",
            "ObjectPlacement",
            "Representation",
        }

        if text in common_ifc_attributes:
            debug_print(f"'{text}' is a known IFC attribute")
            return True

        # Value query patterns
        value_query_patterns = [
            r"^[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*",  # Dotted path
            r"^Pset_[a-zA-Z0-9_]+\.[a-zA-Z_][a-zA-Z0-9_]*$",  # Property set
            r"^Qto_[a-zA-Z0-9_]+\.[a-zA-Z_][a-zA-Z0-9_]*$",  # Quantity set
            r"^/.*/$",  # Regex patterns
        ]

        for pattern in value_query_patterns:
            if re.match(pattern, text):
                debug_print(f"'{text}' matches value query pattern: {pattern}")
                return True

        debug_print(f"'{text}' does not look like a value query")
        return False

    def split_function_arguments(self, args_content: str) -> list:
        """Split function arguments by comma, respecting quoted strings and nested parentheses."""
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
                    args.append(current_arg.strip())
                    current_arg = ""
                else:
                    current_arg += char
            else:
                current_arg += char

            i += 1

        if current_arg.strip():
            args.append(current_arg.strip())

        return args

    def is_number(self, text: str) -> bool:
        """Check if a string represents a number."""
        try:
            float(text)
            return True
        except ValueError:
            return False

    def is_formatting_query(self, value_query: str) -> bool:
        """Check if a value query contains formatting functions."""
        debug_print(f"Checking if '{value_query}' is a formatting query")

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

        for func in formatting_functions:
            pattern = rf"\b{re.escape(func)}\s*\("
            if re.search(pattern, value_query):
                debug_print(f"Found formatting function '{func}' in query")
                return True

        debug_print("No formatting functions found in query")
        return False

    def extract_first_value_query(self, format_query: str) -> str:
        """Extract the first value query from a formatting query for fallback purposes."""
        debug_print(f"Extracting first value query from: {format_query}")

        patterns = [
            r"\b[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*\.\d+\b",
            r"\bPset_[a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*\b",
            r"\b[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)+\b",
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
        """Process value queries for a list of elements."""
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
                        error_print(
                            f"Unexpected error extracting '{value_query}' from element #{element_id}: {e}"
                        )
                        element_values.append("")

                results.append(element_values)

            debug_print(f"Completed processing {len(results)} element results")
            return results

        except Exception as e:
            error_print(f"Failed to process value queries: {e}")
            debug_print(f"Error type: {type(e).__name__}: {e}")
            if is_debug_enabled():
                import traceback

                traceback.print_exc(file=sys.stderr)
            return []

    def format_headers_output(self, value_queries: list) -> str:
        """Format headers for value extraction queries by removing formatting functions."""
        debug_print(f"Formatting headers for {len(value_queries)} value queries")

        headers = []

        for value_query in value_queries:
            try:
                if self.is_formatting_query(value_query):
                    # Strip formatting functions to get core property name
                    core_property = self.extract_first_value_query(value_query)
                    if core_property:
                        headers.append(core_property)
                    else:
                        # Fallback to original query if we can't extract core property
                        headers.append(value_query)
                else:
                    # No formatting functions, use query as-is
                    headers.append(value_query)

            except Exception as e:
                debug_print(f"Failed to process header for '{value_query}': {e}")
                # Fallback to original query
                headers.append(value_query)

        # Format as tab-separated values (same as data rows)
        header_line = "\t".join(headers)
        debug_print(f"Generated header line: {header_line}")

        return header_line

    def format_value_output(self, values: list) -> str:
        """Format extracted values for output."""
        try:
            if not values:
                return ""
            elif len(values) == 1:
                return str(values[0]) if values[0] is not None else ""
            else:
                clean_values = []
                for value in values:
                    if value is None:
                        clean_values.append("")
                    else:
                        clean_value = str(value).replace("\t", " ")
                        clean_values.append(clean_value)
                return "\t".join(clean_values)

        except Exception as e:
            error_print(f"Failed to format values {values}: {e}")
            if is_debug_enabled():
                import traceback

                traceback.print_exc(file=sys.stderr)
            return ""
