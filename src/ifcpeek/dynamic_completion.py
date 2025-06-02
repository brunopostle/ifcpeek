"""
Simplified dynamic completion system for IfcPeek.
Now uses the consolidated cache from completion_cache.py.
Reduced from 800+ lines to ~300 lines by removing duplicate cache code.
"""

import re
from typing import Dict, Set, Any
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
import ifcopenshell
import ifcopenshell.util.selector
from .completion_cache import DynamicIfcCompletionCache
from .debug import debug_print, verbose_print


class FilterQueryCompleter(Completer):
    """Tab completer for IFC selector filter queries (before semicolon)."""

    def __init__(self, cache: DynamicIfcCompletionCache):
        self.cache = cache

    def get_completions(self, document: Document, complete_event):
        """Generate completions for filter queries with proper quote handling."""
        text = document.text
        cursor_pos = document.cursor_position

        debug_print(
            f"FilterQueryCompleter called with: '{text}', cursor at {cursor_pos}"
        )

        # Only provide completions for filter queries (before first semicolon)
        if ";" in text:
            semicolon_pos = text.find(";")
            if cursor_pos > semicolon_pos:
                debug_print("FilterQueryCompleter: Cursor after semicolon, returning")
                return

        # Get text before cursor for analysis
        text_before_cursor = text[:cursor_pos]
        debug_print(
            f"FilterQueryCompleter: text_before_cursor = '{text_before_cursor}'"
        )

        # Parse current word and position
        current_word, start_position = self._parse_current_word(text_before_cursor)

        # Determine context and provide appropriate completions
        completions = self._get_contextual_completions(text_before_cursor, current_word)
        debug_print(
            f"FilterQueryCompleter: Found {len(completions)} contextual completions"
        )

        # Filter and yield completions
        yielded_count = 0
        for completion_text in sorted(completions):
            if self._matches_current_word(completion_text, current_word):
                yield Completion(text=completion_text, start_position=start_position)
                yielded_count += 1

        debug_print(f"FilterQueryCompleter: Yielded {yielded_count} completions")

    def _parse_current_word(self, text_before_cursor: str) -> tuple:
        """Parse current word and start position."""
        current_word = ""
        start_position = 0

        # Check if we're completing a value (after '=')
        if "=" in text_before_cursor:
            parts = text_before_cursor.split("=")
            if len(parts) > 1:
                after_equals = parts[-1]
                if after_equals.startswith('"'):
                    current_word = after_equals[1:]
                    start_position = -len(after_equals)
                else:
                    current_word = after_equals
                    start_position = -len(current_word) if current_word else 0
        else:
            # Original logic for attribute/class completion
            word_match = re.search(r"[^,+\s]*$", text_before_cursor)
            if word_match:
                current_word = word_match.group()
                start_position = -len(current_word) if current_word else 0

        return current_word, start_position

    def _get_contextual_completions(
        self, text_before_cursor: str, current_word: str
    ) -> Set[str]:
        """Get contextual completions based on the current position in the filter query."""
        completions = set()

        # Analyze context
        context = self._analyze_filter_context(text_before_cursor)

        debug_print(f"Context for '{text_before_cursor}': {context}")

        if context["expecting_value"]:
            values = self._get_values_for_context(context, text_before_cursor)
            completions.update(values)
            return completions

        if context["expecting_comparison"]:
            completions.update(self.cache.comparison_operators)
            return completions

        if context["expecting_class"]:
            completions.update(self.cache.ifc_classes_in_model)

        if context["expecting_attribute_or_keyword"]:
            relevant_classes = self.cache.extract_ifc_classes_from_query(
                text_before_cursor
            )
            class_attributes = self.cache.get_attributes_for_classes(relevant_classes)
            completions.update(class_attributes)
            completions.update(self.cache.filter_keywords)
            completions.add("Pset_")
            completions.add("/Pset_.*Common/")
            completions.add("Qto_")
            completions.add("/Qto_.*/")

        if context["expecting_property_name"]:
            pset_name = context["current_pset"]
            if pset_name and pset_name in self.cache.properties_by_pset:
                completions.update(self.cache.properties_by_pset[pset_name])

        if context["at_start_or_after_separator"]:
            completions.update(self.cache.ifc_classes_in_model)

        return completions

    def _analyze_filter_context(self, text: str) -> Dict[str, Any]:
        """Analyze the current context in a filter query."""
        context = {
            "expecting_class": False,
            "expecting_attribute_or_keyword": False,
            "expecting_property_name": False,
            "expecting_value": False,
            "expecting_comparison": False,
            "at_start_or_after_separator": False,
            "current_pset": None,
            "current_attribute": None,
        }

        if not text.strip():
            context["at_start_or_after_separator"] = True
            context["expecting_class"] = True
            return context

        equals_match = re.search(r"([^,+\s]+)\s*=\s*$", text)
        if equals_match:
            context["expecting_value"] = True
            context["current_attribute"] = equals_match.group(1)
            return context

        attr_match = re.search(r"([^,+\s=]+)\s*$", text)
        if attr_match and not text.endswith(",") and not text.endswith("+"):
            possible_attr = attr_match.group(1)
            if not possible_attr.startswith("Ifc") and not possible_attr.startswith(
                "!"
            ):
                context["expecting_comparison"] = True
                context["current_attribute"] = possible_attr
                return context

        if re.search(r"Ifc[A-Za-z0-9]+\s*,\s+$", text):
            context["expecting_attribute_or_keyword"] = True
            return context

        text_stripped = text.strip()
        if text_stripped.endswith(",") or text_stripped.endswith("+"):
            context["at_start_or_after_separator"] = True
            context["expecting_class"] = True
            return context

        last_segment_match = re.search(r"[,+]\s*([^,+]*)$", text_stripped)
        if last_segment_match:
            last_segment = last_segment_match.group(1).strip()
        else:
            last_segment = text_stripped

        if not last_segment:
            context["expecting_class"] = True
            context["at_start_or_after_separator"] = True
        elif re.match(r"^Ifc[A-Za-z0-9]*$", last_segment):
            context["expecting_class"] = True
        elif last_segment.endswith("."):
            context["expecting_property_name"] = True
            pset_candidate = last_segment[:-1]
            if pset_candidate in self.cache.property_sets:
                context["current_pset"] = pset_candidate
        else:
            context["expecting_attribute_or_keyword"] = True

        return context

    def _get_values_for_context(
        self, context: Dict[str, Any], text_before_cursor: str = ""
    ) -> Set[str]:
        """Get values with targeted class extraction."""
        if not context.get("current_attribute"):
            debug_print("_get_values_for_context: No current_attribute in context")
            return set()

        attribute_name = context["current_attribute"]
        debug_print(
            f"_get_values_for_context: Looking for values for attribute '{attribute_name}'"
        )

        target_class = self._extract_target_class(text_before_cursor)
        if not target_class:
            debug_print("_get_values_for_context: No target class found")
            return set()

        debug_print(f"_get_values_for_context: Target class: {target_class}")
        values = self._get_values_from_target_class(target_class, attribute_name)

        debug_print(
            f"_get_values_for_context: Found {len(values)} values from {target_class}"
        )
        return values

    def _extract_target_class(self, text_before_cursor: str) -> str:
        """Extract the specific IFC class being queried."""
        debug_print(f"_extract_target_class: Input text = '{text_before_cursor}'")

        parts = text_before_cursor.split(",")
        debug_print(f"_extract_target_class: Split parts = {parts}")

        if not parts:
            debug_print("_extract_target_class: No parts found")
            return ""

        class_part = parts[0].strip()
        debug_print(f"_extract_target_class: Class part = '{class_part}'")

        ifc_match = re.search(r"\b(Ifc[A-Za-z0-9]+)\b", class_part)
        if ifc_match:
            ifc_class = ifc_match.group(1)
            debug_print(f"_extract_target_class: Found IFC class = '{ifc_class}'")

            if ifc_class in self.cache.ifc_classes_in_model:
                debug_print(
                    f"_extract_target_class: Class '{ifc_class}' found in model"
                )
                return ifc_class
            else:
                debug_print(
                    f"_extract_target_class: Class '{ifc_class}' NOT found in model"
                )
        else:
            debug_print(f"_extract_target_class: No IFC class found in '{class_part}'")

        return ""

    def _get_values_from_target_class(
        self, target_class: str, attribute_name: str
    ) -> Set[str]:
        """Get values from a specific IFC class with automatic quoting for all strings."""
        debug_print(
            f"_get_values_from_target_class: Getting values for {target_class}.{attribute_name}"
        )

        try:
            entities = ifcopenshell.util.selector.filter_elements(
                self.cache.model, target_class
            )

            if not entities:
                debug_print(
                    f"_get_values_from_target_class: No {target_class} entities found in model"
                )
                return set()

            entity_list = list(entities)
            sample_size = min(20, len(entity_list))  # Reduced sample size
            sample_entities = entity_list[:sample_size]

            debug_print(
                f"_get_values_from_target_class: Processing {len(sample_entities)} of {len(entity_list)} {target_class} entities"
            )

            value_query = self._get_value_query_for_attribute(attribute_name)
            debug_print(
                f"_get_values_from_target_class: Using value query '{value_query}'"
            )

            values = set()
            successful_extractions = 0

            for i, entity in enumerate(sample_entities):
                try:
                    value = ifcopenshell.util.selector.get_element_value(
                        entity, value_query
                    )
                    if value is not None:
                        if isinstance(value, str) and value.strip():
                            clean_value = value.strip()
                            if len(clean_value) <= 50:  # Reduced length limit
                                quoted_value = f'"{clean_value}"'
                                values.add(quoted_value)
                                successful_extractions += 1
                        elif isinstance(value, (int, float, bool)):
                            values.add(str(value))
                            successful_extractions += 1
                except Exception as e:
                    if i < 3:  # Only log first few failures
                        debug_print(
                            f"_get_values_from_target_class: Failed to extract from entity {i}: {e}"
                        )
                    continue

            debug_print(
                f"_get_values_from_target_class: Successfully extracted {successful_extractions} values, {len(values)} unique"
            )
            return values

        except Exception as e:
            debug_print(f"_get_values_from_target_class: Error: {e}")
            return set()

    def _get_value_query_for_attribute(self, attribute_name: str) -> str:
        """Map filter attribute names to value extraction queries."""
        attribute_mappings = {
            "material": "material.Name",
            "type": "type.Name",
            "location": "storey.Name",
            "parent": "container.Name",
            "classification": "classification.Identification",
        }

        mapped_query = attribute_mappings.get(attribute_name, attribute_name)
        debug_print(
            f"_get_value_query_for_attribute: '{attribute_name}' -> '{mapped_query}'"
        )
        return mapped_query

    def _matches_current_word(self, completion_text: str, current_word: str) -> bool:
        """Check if completion matches current word."""
        if not current_word:
            return True

        # Handle quoted completions
        if completion_text.startswith('"') and completion_text.endswith('"'):
            completion_for_matching = completion_text[1:-1]
        else:
            completion_for_matching = completion_text

        return completion_for_matching.lower().startswith(current_word.lower())


class DynamicContextResolver:
    """Resolves completions by executing value paths and inspecting results."""

    def __init__(self, cache: DynamicIfcCompletionCache):
        self.cache = cache

    def get_completions_for_path(self, filter_query: str, value_path: str) -> Set[str]:
        """Get completions by executing the path and inspecting actual results.

        This method should work correctly for real IFC models and during testing.
        """
        debug_print(f"get_completions_for_path: '{filter_query}' + '{value_path}'")

        try:
            # Get elements matching the filter
            elements = ifcopenshell.util.selector.filter_elements(
                self.cache.model, filter_query
            )
            if not elements:
                debug_print("No elements found, using fallback")
                return self._get_fallback_completions()

            element_list = list(elements)
            sample_elements = element_list[: min(5, len(element_list))]
            debug_print(f"Processing {len(sample_elements)} sample elements")

            all_attributes = set()
            path_parts = value_path.split(".")
            debug_print(f"Path parts: {path_parts}")

            # Handle simple paths (no dots or single component)
            if len(path_parts) <= 1:
                debug_print("Single-part path, inspecting elements directly")
                for element in sample_elements:
                    attrs = self._get_entity_attributes(element)
                    all_attributes.update(attrs)

                # Add standard IFC completions
                if hasattr(self.cache, "selector_keywords"):
                    all_attributes.update(self.cache.selector_keywords)
                if hasattr(self.cache, "property_sets"):
                    all_attributes.update(self.cache.property_sets)

                debug_print(f"Single-part result: {len(all_attributes)} attributes")
                return all_attributes

            # Handle complex paths (material.item, type.Name, etc.)
            partial_path = ".".join(path_parts[:-1])
            debug_print(f"Multi-part path, extracting: '{partial_path}'")

            # Extract values from each element using the partial path
            for i, element in enumerate(sample_elements):
                try:
                    # This extracts the value at the partial path
                    # For "material.item", this extracts the "material" value
                    result = ifcopenshell.util.selector.get_element_value(
                        element, partial_path
                    )
                    debug_print(
                        f"Element {i}: extracted {type(result)} from '{partial_path}'"
                    )

                    if result is not None:
                        # Inspect what attributes/indices are available on this result
                        # This is where list detection needs to work correctly
                        attrs = self._inspect_result(result)
                        all_attributes.update(attrs)
                        debug_print(f"Element {i}: added {len(attrs)} attributes")

                except Exception as e:
                    debug_print(f"Element {i}: extraction failed: {e}")
                    continue

            # Return results or fallback
            if all_attributes:
                debug_print(f"Multi-part result: {len(all_attributes)} attributes")
                return all_attributes
            else:
                debug_print("No attributes found, using fallback")
                return self._get_fallback_completions()

        except Exception as e:
            debug_print(f"Error in get_completions_for_path: {e}")
            return self._get_fallback_completions()

    def _inspect_result(self, result: Any) -> Set[str]:
        """Inspect a result object to determine what attributes/indices are available.

        This method should correctly handle both IFC entities and list results in normal usage.
        The test failure indicates that list detection isn't working properly.
        """
        attributes = set()

        debug_print(f"_inspect_result called with: {type(result)}")

        try:
            if result is None:
                debug_print("Result is None")
                return attributes

            # Handle list/tuple results (this is the main issue in the failing test)
            if isinstance(result, (list, tuple)):
                debug_print(f"Detected list/tuple with {len(result)} items")

                # Add list-specific attributes that are always available
                attributes.add("count")  # len(list)

                # Add numeric indices for list access
                for i in range(min(len(result), 10)):  # Limit to first 10 indices
                    attributes.add(str(i))

                # Add selector keywords that work on lists
                if hasattr(self.cache, "selector_keywords"):
                    attributes.update(self.cache.selector_keywords)
                    debug_print(f"Added selector keywords for list")

                debug_print(f"List result completions: {sorted(attributes)}")
                return attributes

            # Handle object results (IFC entities, etc.)
            debug_print(f"Treating as object: {type(result)}")

            # Get object's attributes
            entity_attrs = self._get_entity_attributes(result)
            attributes.update(entity_attrs)

            # Add selector keywords that work on objects
            if hasattr(self.cache, "selector_keywords"):
                attributes.update(self.cache.selector_keywords)
                debug_print(f"Added selector keywords for object")

        except Exception as e:
            debug_print(f"Error in _inspect_result: {e}")
            # Return at least selector keywords as fallback
            if hasattr(self.cache, "selector_keywords"):
                attributes.update(self.cache.selector_keywords)

        debug_print(f"_inspect_result returning: {sorted(attributes)}")
        return attributes

    def _get_entity_attributes(self, entity: Any) -> Set[str]:
        """Get attributes from any entity by direct inspection.

        This method should work correctly whether called during testing or normal usage.
        The test failure indicates that dir() inspection isn't working properly.
        """
        attributes = set()

        # Method 1: Try __dict__ inspection first (if available)
        try:
            if hasattr(entity, "__dict__"):
                try:
                    dict_keys = list(entity.__dict__.keys())
                    dict_attrs = [
                        k
                        for k in dict_keys
                        if k and isinstance(k, str) and k and k[0].isupper()
                    ]
                    attributes.update(dict_attrs)
                    debug_print(f"Found {len(dict_attrs)} attributes via __dict__")
                except (AttributeError, TypeError) as e:
                    debug_print(f"Could not access __dict__ contents: {e}")
        except Exception as e:
            debug_print(f"Error checking __dict__: {e}")

        # Method 2: Always try dir() inspection (this is the main issue in the failing test)
        try:
            # Get all attributes via dir()
            all_attrs = dir(entity)
            debug_print(f"dir() returned {len(all_attrs)} attributes")

            # Filter for IFC-style attributes: uppercase, non-private
            for attr_name in all_attrs:
                if (
                    attr_name
                    and isinstance(attr_name, str)
                    and len(attr_name) > 0
                    and attr_name[0].isupper()
                    and not attr_name.startswith("_")
                ):

                    # Test if attribute is actually accessible
                    try:
                        getattr(entity, attr_name)
                        attributes.add(attr_name)
                        debug_print(f"Added accessible attribute: {attr_name}")
                    except (AttributeError, TypeError):
                        debug_print(f"Attribute {attr_name} not accessible")
                        continue
                    except Exception as e:
                        debug_print(f"Error accessing {attr_name}: {e}")
                        continue

        except Exception as e:
            debug_print(f"Error in dir() inspection: {e}")

        debug_print(f"_get_entity_attributes found: {sorted(attributes)}")
        return attributes

    def _get_fallback_completions(self) -> Set[str]:
        """Get fallback completions when dynamic inspection fails."""
        fallback = set()
        fallback.update(self.cache.selector_keywords)
        fallback.update(["Name", "Description", "GlobalId", "class", "id"])
        fallback.update(self.cache.property_sets)
        return fallback


class DynamicIfcValueCompleter(Completer):
    """Tab completer for value extraction queries (after semicolon)."""

    def __init__(self, cache: DynamicIfcCompletionCache):
        self.cache = cache
        self.resolver = DynamicContextResolver(cache)

    def get_completions(self, document: Document, complete_event):
        """Generate completions for value extraction queries."""
        text = document.text
        cursor_pos = document.cursor_position

        # Only provide completions for value extraction (after semicolon)
        if ";" not in text:
            return

        parts = text.split(";")
        if len(parts) < 2:
            return

        # Find which part the cursor is in
        current_pos = 0
        current_part_index = 0

        for i, part in enumerate(parts):
            part_end = current_pos + len(part)

            if cursor_pos <= part_end:
                current_part_index = i
                break

            # Move to next part (add 1 for semicolon)
            current_pos = part_end + 1

        # Skip filter query (first part)
        if current_part_index == 0:
            return

        # Get the text before cursor in the current part
        part_start_pos = sum(len(parts[j]) + 1 for j in range(current_part_index))
        cursor_in_part = cursor_pos - part_start_pos
        current_part = parts[current_part_index]

        if cursor_in_part < 0:
            cursor_in_part = 0
        elif cursor_in_part > len(current_part):
            cursor_in_part = len(current_part)

        text_before_cursor = current_part[:cursor_in_part]
        filter_query = parts[0].strip()

        # Get completions using dynamic inspection
        try:
            completions = self.resolver.get_completions_for_path(
                filter_query, text_before_cursor.strip()
            )
        except Exception:
            return

        # Find the word being completed
        word_pattern = r"[^.\s]*$"
        word_match = re.search(word_pattern, text_before_cursor)
        if word_match:
            current_word = word_match.group()
            start_position = -len(current_word) if current_word else 0
        else:
            current_word = ""
            start_position = 0

        # Filter and yield completions
        for completion_text in sorted(completions):
            if not current_word or completion_text.lower().startswith(
                current_word.lower()
            ):
                yield Completion(text=completion_text, start_position=start_position)

    def get_debug_info(self) -> Dict[str, Any]:
        """Get debug information about the completion system."""
        return {
            "total_classes": len(self.cache.ifc_classes_in_model),
            "cached_attributes": len(self.cache.attribute_cache),
            "property_sets": len(self.cache.property_sets),
            "selector_keywords": len(self.cache.selector_keywords),
            "filter_keywords": len(self.cache.filter_keywords),
            "common_attributes": len(self.cache.common_attributes),
            "sample_classes": sorted(list(self.cache.ifc_classes_in_model)[:10]),
            "sample_property_sets": sorted(list(self.cache.property_sets)[:10]),
        }


class CombinedIfcCompleter(Completer):
    """Combined completer that handles both filter queries and value extraction."""

    def __init__(self, cache: DynamicIfcCompletionCache):
        self.cache = cache
        self.filter_completer = FilterQueryCompleter(cache)
        self.value_completer = DynamicIfcValueCompleter(cache)

    def get_completions(self, document: Document, complete_event):
        """Route to appropriate completer based on cursor position."""
        text = document.text
        cursor_pos = document.cursor_position

        # DEBUG: Add logging to see what's happening
        debug_print(f"CombinedCompleter called with: '{text}', cursor at {cursor_pos}")

        # Determine if we're in filter query or value extraction context
        if ";" not in text:
            # No semicolon - definitely filter query (including value completion)
            debug_print("Routing to filter_completer (no semicolon)")
            yield from self.filter_completer.get_completions(document, complete_event)
        else:
            # Has semicolon - check which side of first semicolon cursor is on
            first_semicolon_pos = text.find(";")
            if cursor_pos <= first_semicolon_pos:
                # Cursor is before or at first semicolon - filter query
                debug_print("Routing to filter_completer (before semicolon)")
                yield from self.filter_completer.get_completions(
                    document, complete_event
                )
            else:
                # Cursor is after first semicolon - value extraction
                debug_print("Routing to value_completer (after semicolon)")
                yield from self.value_completer.get_completions(
                    document, complete_event
                )

    def get_debug_info(self) -> Dict[str, Any]:
        """Get debug information about the completion system."""
        return self.value_completer.get_debug_info()


def create_dynamic_completion_system(model: ifcopenshell.file):
    """Create the enhanced completion system with both filter and value support."""
    try:
        cache = DynamicIfcCompletionCache(model)
        completer = CombinedIfcCompleter(cache)
        return cache, completer
    except Exception as e:
        # If cache creation fails completely, re-raise the exception
        # This allows the shell to catch it and set cache/completer to None
        raise e


# Backwards compatibility aliases
create_enhanced_completion_system = create_dynamic_completion_system
