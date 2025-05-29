"""Output formatting and syntax highlighting for IfcPeek."""

import os
import re
import sys


class StepHighlighter:
    """Syntax highlighter for STEP (SPF) format output."""

    # ANSI color codes
    COLORS = {
        "reset": "\033[0m",
        "entity_id": "\033[94m",  # Blue for #123
        "entity_type": "\033[92m",  # Green for IFCWALL
        "string": "\033[93m",  # Yellow for 'quoted strings'
        "guid": "\033[96m",  # Cyan for GUIDs
        "number": "\033[95m",  # Magenta for numbers
        "operator": "\033[90m",  # Gray for = $ , ; ( )
    }

    def __init__(self):
        self.enabled = self._should_enable_colors()

    def _should_enable_colors(self) -> bool:
        """Determine if colors should be enabled."""
        if "FORCE_COLOR" in os.environ:
            return True
        if "NO_COLOR" in os.environ:
            return False
        if not sys.stdout.isatty():
            return False
        term = os.environ.get("TERM", "")
        if term in ("dumb", ""):
            return False
        return True

    def _colorize(self, text: str, color_key: str) -> str:
        """Apply color to text if colors are enabled."""
        if not self.enabled:
            return text
        return f"{self.COLORS[color_key]}{text}{self.COLORS['reset']}"

    def highlight_step_line(self, line: str) -> str:
        """Apply syntax highlighting to a single STEP format line."""
        if not self.enabled or not line.strip():
            return line

        # STEP format pattern: #123=IFCWALL('guid',$,$,'name',...);
        step_pattern = r"^(#\d+)(=)([A-Z][A-Za-z0-9_]*)\((.*)\);?\s*$"
        match = re.match(step_pattern, line.strip())

        if not match:
            return line

        entity_id, equals, entity_type, parameters = match.groups()

        # Colorize components
        colored_id = self._colorize(entity_id, "entity_id")
        colored_equals = self._colorize(equals, "operator")
        colored_type = self._colorize(entity_type, "entity_type")
        colored_params = self._highlight_parameters(parameters)

        result = f"{colored_id}{colored_equals}{colored_type}({colored_params});"

        if line.endswith("\n"):
            result += "\n"

        return result

    def _highlight_parameters(self, params: str) -> str:
        """Highlight parameters within STEP entity definition."""
        if not params:
            return params

        result = []
        i = 0

        while i < len(params):
            char = params[i]

            # Handle quoted strings
            if char == "'":
                start = i
                i += 1
                while i < len(params):
                    if params[i] == "'":
                        if i + 1 < len(params) and params[i + 1] == "'":
                            i += 2  # Skip escaped quote
                        else:
                            i += 1
                            break
                    else:
                        i += 1

                string_content = params[start:i]
                if self._is_guid_string(string_content):
                    result.append(self._colorize(string_content, "guid"))
                else:
                    result.append(self._colorize(string_content, "string"))

            # Handle numbers
            elif char.isdigit() or (
                char == "-" and i + 1 < len(params) and params[i + 1].isdigit()
            ):
                start = i
                if char == "-":
                    i += 1
                while i < len(params) and (params[i].isdigit() or params[i] in ".eE+-"):
                    i += 1

                number = params[start:i]
                result.append(self._colorize(number, "number"))

            # Handle operators
            elif char in "=$,();":
                result.append(self._colorize(char, "operator"))
                i += 1

            # Handle entity references (#123)
            elif char == "#":
                start = i
                i += 1
                while i < len(params) and params[i].isdigit():
                    i += 1
                reference = params[start:i]
                result.append(self._colorize(reference, "entity_id"))

            else:
                result.append(char)
                i += 1

        return "".join(result)

    def _is_guid_string(self, string_with_quotes: str) -> bool:
        """Check if a quoted string contains a GUID."""
        content = string_with_quotes.strip("'")

        # Common GUID patterns
        patterns = [
            r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
            r"^[0-9a-zA-Z_$]{22}",  # IFC compressed GUID
        ]

        return any(re.match(pattern, content) for pattern in patterns)


def format_query_results(entities, enable_highlighting=True):
    """Format a list of IFC entities for display.

    Args:
        entities: List of IFC entities to format
        enable_highlighting: Whether to apply syntax highlighting

    Returns:
        Generator yielding formatted entity strings
    """
    if not entities:
        return

    highlighter = StepHighlighter() if enable_highlighting else None

    for entity in entities:
        try:
            # Convert entity to SPF format (Step Physical File format)
            spf_line = str(entity)

            # Apply syntax highlighting if enabled
            if highlighter and highlighter.enabled:
                highlighted_line = highlighter.highlight_step_line(spf_line)
                yield highlighted_line
            else:
                yield spf_line

        except Exception as entity_error:
            # Log error to stderr but don't break the output stream
            print(
                f"ERROR: Failed to format entity: {type(entity_error).__name__}: {entity_error}",
                file=sys.stderr,
            )
            # Yield a fallback representation
            yield f"<Entity formatting error: {type(entity).__name__}>"


def format_element_value(value, format_spec=None):
    """Format an element value according to the specified format.

    This function will be enhanced to support the IfcOpenShell selector
    formatting syntax like upper(), lower(), round(), etc.

    Args:
        value: The value to format
        format_spec: Optional formatting specification

    Returns:
        Formatted string representation of the value
    """
    if value is None:
        return ""

    # Basic formatting for now - will be enhanced for selector formatting syntax
    if format_spec:
        # Future: Parse and apply format_spec (upper, lower, round, etc.)
        pass

    return str(value)
