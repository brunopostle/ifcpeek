"""
Simplified dynamic completion system for IfcPeek.
Now uses the consolidated cache from completion_cache.py.
Reduced from 800+ lines to ~300 lines by removing duplicate cache code.
"""

import re
import sys
from typing import Dict, Set, Any
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
import ifcopenshell
import ifcopenshell.util.selector
import ifcopenshell.util.element
from .completion_cache import DynamicIfcCompletionCache
from .debug import debug_print


class FilterQueryCompleter(Completer):
    """Fixed filter query completer with proper property set support."""

    def __init__(self, cache):
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
        """Parse current word and start position with proper handling."""
        current_word = ""
        start_position = 0

        # Check for comparison patterns first (after = > < etc.)
        comparison_match = re.search(
            r"(\w+)\s*(>=|<=|!=|\*=|!\*=|>|<|=)\s*(.*)$", text_before_cursor
        )
        if comparison_match:
            partial_value = comparison_match.group(3)  # What comes after the operator
            current_word = partial_value
            start_position = -len(partial_value) if partial_value else 0
            debug_print(
                f"Parsed comparison: current_word='{current_word}', start_position={start_position}"
            )
            return current_word, start_position

        # Check for property set completion patterns
        # Pattern: "IfcClass, PropertySet."
        pset_dot_pattern = r"(Ifc[A-Za-z0-9]+)\s*,\s*([A-Za-z0-9_]+)\.\s*$"
        pset_dot_match = re.search(pset_dot_pattern, text_before_cursor)
        if pset_dot_match:
            debug_print("Parsed property set dot pattern")
            current_word = ""
            start_position = 0
            return current_word, start_position

        # Handle negation patterns
        space_negation = re.search(r"!\s+([A-Za-z]*)$", text_before_cursor)
        if space_negation:
            current_word = space_negation.group(1)
            start_position = -len(current_word) if current_word else 0
            return current_word, start_position

        no_space_negation = re.search(r"!([A-Za-z]+)$", text_before_cursor)
        if no_space_negation:
            current_word = no_space_negation.group(1)
            start_position = -len(current_word)
            return current_word, start_position

        if text_before_cursor.endswith("!") or re.search(r"!\s+$", text_before_cursor):
            current_word = ""
            start_position = 0
            return current_word, start_position

        # Default word parsing
        word_match = re.search(r"[^,+\s]*$", text_before_cursor)
        if word_match:
            current_word = word_match.group()
            start_position = -len(current_word) if current_word else 0

        return current_word, start_position

    def _get_contextual_completions(
        self, text_before_cursor: str, current_word: str
    ) -> Set[str]:
        """Enhanced to handle all property set completion scenarios - FIXED basic completion regression."""
        completions = set()

        debug_print(f"Getting contextual completions for: '{text_before_cursor}'")

        # Check if we're in a negation context first
        if re.search(r"!\s*[A-Za-z]*$", text_before_cursor):
            completions.update(self.cache.ifc_classes_in_model)
            return completions

        # Check for property set name completion in filter context
        # Pattern: "IfcClass, Qto_" or "IfcClass, Pset_"
        pset_name_pattern = r"(Ifc[A-Za-z0-9]+)\s*,\s*([PQE][a-zA-Z0-9_]*)\s*$"
        pset_name_match = re.search(pset_name_pattern, text_before_cursor)

        if pset_name_match:
            ifc_class = pset_name_match.group(1)
            pset_prefix = pset_name_match.group(2)
            debug_print(
                f"Detected filter property set name completion: {ifc_class}, {pset_prefix}"
            )

            matching_psets = self._get_filter_matching_property_set_names(
                ifc_class, pset_prefix
            )
            if matching_psets:
                completions.update(matching_psets)
                debug_print(
                    f"Found {len(matching_psets)} matching property sets for filter"
                )
                return completions

        # Check for property set property completion pattern
        # Pattern: "IfcClass, Pset_Name." or "IfcClass, Qto_Name."
        pset_completion_pattern = r"(Ifc[A-Za-z0-9]+)\s*,\s*([PQE][a-zA-Z0-9_]+)\.\s*$"
        pset_match = re.search(pset_completion_pattern, text_before_cursor)

        if pset_match:
            ifc_class = pset_match.group(1)
            pset_name = pset_match.group(2)
            debug_print(
                f"Detected property set property completion: {ifc_class}, {pset_name}."
            )

            pset_properties = self._get_filter_property_set_properties(
                ifc_class, pset_name
            )
            if pset_properties:
                completions.update(pset_properties)
                debug_print(f"Found {len(pset_properties)} properties for {pset_name}")
                return completions

        # Check for value completion (after comparison operators)
        value_pattern = r"(\w+)\s*(>=|<=|!=|\*=|!\*=|>|<|=)\s*(.*)$"
        value_match = re.search(value_pattern, text_before_cursor)

        if value_match:
            attribute = value_match.group(1)
            operator = value_match.group(2)
            debug_print(
                f"Detected value completion: attr='{attribute}', op='{operator}'"
            )

            values = self._get_values_for_filter_context(text_before_cursor, attribute)
            if values:
                completions.update(values)
                debug_print(f"Found {len(values)} values for {attribute}")
                return completions

        # REGRESSION FIX 2: Enhanced basic completion after comma
        # Check for basic completion after "IfcClass, " pattern
        basic_completion_pattern = r"(Ifc[A-Za-z0-9]+)\s*,\s*$"
        basic_match = re.search(basic_completion_pattern, text_before_cursor)

        if basic_match:
            ifc_class = basic_match.group(1)
            debug_print(f"Detected basic completion after: {ifc_class}, ")

            # Add IFC classes (for union queries like "IfcWall, IfcSlab")
            completions.update(self.cache.ifc_classes_in_model)

            # Add filter keywords
            completions.update(self.cache.filter_keywords)

            # Add class-specific attributes
            relevant_classes = {ifc_class}
            class_attributes = self.cache.get_attributes_for_classes(relevant_classes)
            completions.update(class_attributes)

            # Add property set prefixes
            completions.add("Pset_")
            completions.add("/Pset_.*Common/")
            completions.add("Qto_")
            completions.add("/Qto_.*/")

            # Add actual property sets that exist for this class
            try:
                elements = ifcopenshell.util.selector.filter_elements(
                    self.cache.model, ifc_class
                )
                if elements:
                    sample_elements = list(elements)[:3]
                    for element in sample_elements:
                        try:
                            all_psets = ifcopenshell.util.element.get_psets(element)
                            for pset_name in all_psets.keys():
                                completions.add(pset_name)
                        except Exception:
                            continue
            except Exception:
                pass

            debug_print(f"Basic completion: added {len(completions)} completions")
            return completions

        # Original contextual completion logic for other cases
        context = self._analyze_filter_context(text_before_cursor)
        debug_print(f"Context analysis: {context}")

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

    def _get_filter_property_set_properties(
        self, ifc_class: str, pset_name: str
    ) -> Set[str]:
        """Get properties for a property set in filter context."""
        debug_print(f"Getting filter properties for {ifc_class}.{pset_name}")

        properties = set()

        try:
            # Get elements of the specified IFC class
            elements = ifcopenshell.util.selector.filter_elements(
                self.cache.model, ifc_class
            )

            if not elements:
                debug_print(f"No {ifc_class} elements found in model")
                return self._get_cached_property_set_properties(pset_name)

            # Sample a few elements
            sample_elements = list(elements)[:5]
            debug_print(f"Sampling {len(sample_elements)} {ifc_class} elements")

            for element in sample_elements:
                try:
                    # Get all property sets for this element
                    all_psets = ifcopenshell.util.element.get_psets(element)

                    if pset_name in all_psets:
                        pset_data = all_psets[pset_name]
                        debug_print(
                            f"Found {pset_name} with properties: {list(pset_data.keys())}"
                        )

                        for prop_name in pset_data.keys():
                            if prop_name != "id":
                                properties.add(prop_name)
                                debug_print(f"Added filter property: {prop_name}")

                except Exception as e:
                    debug_print(f"Failed to get property sets for element: {e}")
                    continue

            if properties:
                debug_print(
                    f"Found {len(properties)} filter properties in {pset_name}: {sorted(properties)}"
                )
                return properties
            else:
                debug_print(f"No filter properties found for {pset_name}, trying cache")
                return self._get_cached_property_set_properties(pset_name)

        except Exception as e:
            debug_print(f"Error getting filter property set properties: {e}")
            return self._get_cached_property_set_properties(pset_name)

    def _get_filter_matching_property_set_names(
        self, ifc_class: str, prefix: str
    ) -> Set[str]:
        """Get property set names matching prefix for filter queries."""
        debug_print(
            f"Getting filter property set names for {ifc_class} matching '{prefix}'"
        )

        matching_names = set()

        try:
            elements = ifcopenshell.util.selector.filter_elements(
                self.cache.model, ifc_class
            )

            if not elements:
                debug_print(f"No {ifc_class} elements found in model")
                cached_matches = {
                    name for name in self.cache.property_sets if name.startswith(prefix)
                }
                return cached_matches

            sample_elements = list(elements)[:5]
            debug_print(f"Sampling {len(sample_elements)} {ifc_class} elements")

            for element in sample_elements:
                try:
                    all_psets = ifcopenshell.util.element.get_psets(element)

                    for pset_name in all_psets.keys():
                        if pset_name.startswith(prefix):
                            matching_names.add(pset_name)
                            debug_print(
                                f"Found matching filter property set: {pset_name}"
                            )

                except Exception as e:
                    debug_print(f"Failed to get property sets for element: {e}")
                    continue

            debug_print(
                f"Found {len(matching_names)} matching filter property sets: {sorted(matching_names)}"
            )
            return matching_names

        except Exception as e:
            debug_print(f"Error getting filter property set names: {e}")
            cached_matches = {
                name for name in self.cache.property_sets if name.startswith(prefix)
            }
            return cached_matches

    def _get_cached_property_set_properties(self, pset_name: str) -> Set[str]:
        """Get properties from the cache for a property set."""
        if (
            hasattr(self.cache, "properties_by_pset")
            and pset_name in self.cache.properties_by_pset
        ):
            cached_props = self.cache.properties_by_pset[pset_name]
            debug_print(f"Using cached properties for {pset_name}: {cached_props}")
            return cached_props
        else:
            debug_print(f"No cached properties found for {pset_name}")
            return set()

    def _get_values_for_filter_context(
        self, text_before_cursor: str, attribute: str
    ) -> Set[str]:
        """Get values for filter context - FIX: Check boolean type FIRST."""
        debug_print(f"Getting values for filter context: attribute='{attribute}'")

        values = set()

        try:
            # Parse the full query to understand the context
            # Extract IFC class
            parts = text_before_cursor.split(",")
            if not parts:
                debug_print("No parts found in text")
                return set()

            class_part = parts[0].strip()
            ifc_match = re.search(r"\b(Ifc[A-Za-z0-9]+)\b", class_part)

            if not ifc_match:
                debug_print(f"No IFC class found in '{class_part}'")
                return set()

            ifc_class = ifc_match.group(1)
            debug_print(f"Extracted IFC class: {ifc_class}")

            # Extract the full attribute path
            full_attr_match = re.search(
                r",\s*([A-Za-z0-9_]+\.[A-Za-z0-9_]+)\s*[>=<!]", text_before_cursor
            )

            if full_attr_match:
                full_attribute_path = full_attr_match.group(1)
                debug_print(f"Found full attribute path: {full_attribute_path}")
            else:
                # Fallback: if it's just the property name, try common mappings
                full_attribute_path = self._map_attribute_to_query_path(
                    attribute, text_before_cursor
                )
                debug_print(
                    f"Mapped attribute to path: {attribute} -> {full_attribute_path}"
                )

            # Get elements
            elements = ifcopenshell.util.selector.filter_elements(
                self.cache.model, ifc_class
            )
            debug_print(f"Found {len(elements)} {ifc_class} elements")

            if not elements:
                return set()

            # Sample ALL elements to find boolean values
            all_elements = list(elements)
            debug_print(
                f"Sampling ALL {len(all_elements)} elements to find property values"
            )

            found_boolean = False
            values_with_data = 0

            for i, element in enumerate(all_elements):
                try:
                    # Try to extract the value using the full attribute path
                    value = ifcopenshell.util.selector.get_element_value(
                        element, full_attribute_path
                    )

                    if value is not None:
                        values_with_data += 1

                        # Log first few values for debugging
                        if values_with_data <= 5:
                            debug_print(
                                f"Element {i}: {full_attribute_path} = {value} (type: {type(value)})"
                            )

                        # FIX: Check boolean type FIRST before other types
                        if isinstance(value, bool):
                            if not found_boolean:  # Only log once
                                debug_print(
                                    f"BOOLEAN DETECTION: Found boolean value {value} at element {i}"
                                )
                            found_boolean = True
                            # Don't add to values yet - we'll handle this at the end
                        elif isinstance(value, str) and value.strip():
                            quoted_value = f'"{value.strip()}"'
                            values.add(quoted_value)
                            debug_print(f"Added string value: {quoted_value}")
                        elif isinstance(value, (int, float)):
                            quoted_value = f'"{str(value)}"'
                            values.add(quoted_value)
                            debug_print(f"Added numeric value: {quoted_value}")
                        else:
                            debug_print(f"Unknown value type: {type(value)} = {value}")

                except Exception as e:
                    # Only log first few failures to avoid spam
                    if i < 3:
                        debug_print(f"Element {i}: extraction failed: {e}")
                    continue

            debug_print(
                f"Sampling complete: found_boolean = {found_boolean}, values_with_data = {values_with_data}"
            )
            debug_print(f"Values collected before boolean check: {values}")

            # If we found ANY boolean values, this is a boolean property
            if found_boolean:
                debug_print(
                    "BOOLEAN DETECTION SUCCESS: Clearing other values and offering TRUE/FALSE"
                )
                values.clear()  # Clear any other values
                values.add("TRUE")
                values.add("FALSE")
                debug_print("Added TRUE and FALSE options")
                return values

            # Return whatever non-boolean values we found
            debug_print(f"Final non-boolean values: {list(values)}")
            return values

        except Exception as e:
            debug_print(f"Error in value extraction: {e}")
            import traceback

            traceback.print_exc(file=sys.stderr)
            return set()

    def _map_attribute_to_query_path(
        self, attribute: str, text_before_cursor: str
    ) -> str:
        """Map simple attribute names to full query paths based on context."""

        # Check if we're in a property set context
        # Look for pattern like "IfcBeam, Qto_BeamBaseQuantities.Length"
        pset_attr_match = re.search(
            r",\s*([A-Za-z0-9_]+)\." + re.escape(attribute), text_before_cursor
        )

        if pset_attr_match:
            pset_name = pset_attr_match.group(1)
            full_path = f"{pset_name}.{attribute}"
            debug_print(f"Mapped to property set path: {full_path}")
            return full_path

        # Default mappings for common attributes
        attribute_mappings = {
            "material": "material.Name",
            "type": "type.Name",
            "location": "storey.Name",
            "parent": "container.Name",
            "classification": "classification.Identification",
        }

        mapped_path = attribute_mappings.get(attribute, attribute)
        debug_print(f"Mapped to default path: {attribute} -> {mapped_path}")
        return mapped_path

    def _analyze_filter_context(self, text: str) -> Dict[str, Any]:
        """Enhanced context analysis to handle property set patterns better."""
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

        # Check for property set pattern with dot: "IfcClass, Pset_Name."
        pset_dot_pattern = r"(Ifc[A-Za-z0-9]+)\s*,\s*([PQE][a-zA-Z0-9_]+)\.\s*$"
        pset_dot_match = re.search(pset_dot_pattern, text)
        if pset_dot_match:
            context["expecting_property_name"] = True
            context["current_pset"] = pset_dot_match.group(2)
            debug_print(
                f"Context: expecting property name for {context['current_pset']}"
            )
            return context

        # Check for value completion (after '=', '>' etc..)
        comparison_match = re.search(
            r"(\w+)\s*(>=|<=|!=|\*=|!\*=|>|<|=)\s*(.*?)$", text
        )

        if comparison_match:
            context["expecting_value"] = True
            context["current_attribute"] = comparison_match.group(1)
            context["partial_value"] = comparison_match.group(3)
            return context

        # Pattern: "IfcClass, PartialWord" where PartialWord could be partial attribute
        ifc_comma_pattern = r"Ifc[A-Za-z0-9]+\s*,\s*([A-Za-z_][A-Za-z0-9_]*)\s*$"
        ifc_comma_match = re.search(ifc_comma_pattern, text)
        if ifc_comma_match:
            word_after_comma = ifc_comma_match.group(1)

            complete_keywords = {
                "material",
                "type",
                "location",
                "parent",
                "classification",
                "query",
            }

            if word_after_comma in complete_keywords:
                context["expecting_comparison"] = True
                context["current_attribute"] = word_after_comma
            else:
                context["expecting_attribute_or_keyword"] = True

            return context

        # Check for attribute completion after comma + space (no partial word yet)
        if re.search(r"Ifc[A-Za-z0-9]+\s*,\s+$", text):
            context["expecting_attribute_or_keyword"] = True
            return context

        # Check for comparison operator expectation
        attr_match = re.search(r"([^,+\s=]+)\s*$", text)
        if attr_match and not text.endswith(",") and not text.endswith("+"):
            possible_attr = attr_match.group(1)
            if not possible_attr.startswith("Ifc") and not possible_attr.startswith(
                "!"
            ):
                context["expecting_comparison"] = True
                context["current_attribute"] = possible_attr
                return context

        # Rest of the original logic...
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
            context["current_pset"] = pset_candidate
        else:
            context["expecting_attribute_or_keyword"] = True

        return context

    def _get_values_for_context(
        self, context: Dict[str, Any], text_before_cursor: str = ""
    ) -> Set[str]:
        """Get values with targeted class extraction - Simplified without heuristics."""
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

            # Try extracting from the context again
            parts = text_before_cursor.split(",")
            if parts:
                class_part = parts[0].strip()
                ifc_match = re.search(r"\b(Ifc[A-Za-z0-9]+)\b", class_part)
                if ifc_match:
                    target_class = ifc_match.group(1)
                    debug_print(
                        f"_get_values_for_context: Retry found class: {target_class}"
                    )

        if not target_class:
            debug_print("_get_values_for_context: Still no target class found")
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
        """Get values from a specific IFC class - FIX: Check boolean type FIRST."""
        debug_print(
            f"_get_values_from_target_class: Getting values for {target_class}.{attribute_name}"
        )

        try:
            elements = ifcopenshell.util.selector.filter_elements(
                self.cache.model, target_class
            )

            if not elements:
                debug_print(
                    f"_get_values_from_target_class: No {target_class} entities found in model"
                )
                return set()

            # Process ALL elements
            all_elements = list(elements)
            debug_print(
                f"_get_values_from_target_class: Processing ALL {len(all_elements)} {target_class} entities"
            )

            value_query = self._get_value_query_for_attribute(attribute_name)
            debug_print(
                f"_get_values_from_target_class: Using value query '{value_query}'"
            )

            values = set()
            successful_extractions = 0
            found_boolean = False

            for i, entity in enumerate(all_elements):
                try:
                    value = ifcopenshell.util.selector.get_element_value(
                        entity, value_query
                    )
                    if value is not None:
                        successful_extractions += 1

                        # Log first few values for debugging
                        if successful_extractions <= 5:
                            debug_print(
                                f"Entity {i}: {value_query} = {value} (type: {type(value)})"
                            )

                        # FIX: Check boolean type FIRST before other types
                        if isinstance(value, bool):
                            if not found_boolean:  # Only log once
                                debug_print(
                                    f"BOOLEAN DETECTION: Found boolean value {value} at entity {i}"
                                )
                            found_boolean = True
                            # Don't add to values yet - we'll handle this at the end
                        elif isinstance(value, str) and value.strip():
                            clean_value = value.strip()
                            if len(clean_value) <= 50:
                                quoted_value = f'"{clean_value}"'
                                values.add(quoted_value)
                        elif isinstance(value, (int, float)):
                            quoted_value = f'"{str(value)}"'
                            values.add(quoted_value)

                except Exception as e:
                    # Only log first few failures to avoid spam
                    if i < 3:
                        debug_print(
                            f"_get_values_from_target_class: Failed to extract from entity {i}: {e}"
                        )
                    continue

            debug_print(
                f"_get_values_from_target_class: found_boolean = {found_boolean}, successful_extractions = {successful_extractions}"
            )

            # If we found ANY boolean values, this is a boolean property
            if found_boolean:
                debug_print(
                    "BOOLEAN DETECTION SUCCESS: Clearing other values and offering TRUE/FALSE"
                )
                values.clear()  # Clear any other values
                values.add("TRUE")
                values.add("FALSE")

            debug_print(f"_get_values_from_target_class: Final values: {list(values)}")
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
        """Get completions by executing the path and inspecting actual results."""
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

            # Handle property set name completion
            # Case: "Qto_", "Pset_", "EPset_" (partial property set names)
            if len(path_parts) == 1 and (
                value_path.startswith("Qto_")
                or value_path.startswith("Pset_")
                or value_path.startswith("EPset_")
            ):

                debug_print(
                    f"Detected property set name completion for: '{value_path}'"
                )
                matching_psets = self._get_matching_property_set_names(
                    sample_elements, value_path
                )

                if matching_psets:
                    debug_print(f"Found {len(matching_psets)} matching property sets")
                    return matching_psets
                else:
                    debug_print(
                        "No matching property sets found, trying cache fallback"
                    )
                    # Fallback to cached property sets
                    cached_matches = {
                        name
                        for name in self.cache.property_sets
                        if name.startswith(value_path)
                    }
                    if cached_matches:
                        return cached_matches

            # Handle property set completion specifically
            elif len(path_parts) == 2 and path_parts[1] == "":
                # Case: "Qto_BeamBaseQuantities." (with trailing dot)
                pset_name = path_parts[0]
                debug_print(
                    f"Detected property set property completion for: {pset_name}"
                )
                return self._get_property_set_properties(sample_elements, pset_name)

            elif len(path_parts) == 1 and (
                value_path.startswith("Pset_")
                or value_path.startswith("Qto_")
                or value_path.startswith("EPset_")
            ):
                # Case: "Qto_BeamBaseQuantities" (no trailing dot yet)
                # Check if this is a complete property set name
                debug_print(
                    f"Checking if '{value_path}' is a complete property set name"
                )

                complete_pset_names = self._find_complete_property_set_names(
                    sample_elements, value_path
                )
                if complete_pset_names:
                    # Return property set names that match the prefix
                    return complete_pset_names
                else:
                    # Try to get properties for this property set name
                    return self._get_property_set_properties(
                        sample_elements, value_path
                    )

            # Handle simple paths (no dots or single component)
            elif len(path_parts) <= 1:
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
            else:
                partial_path = ".".join(path_parts[:-1])
                debug_print(f"Multi-part path, extracting: '{partial_path}'")

                # Extract values from each element using the partial path
                for i, element in enumerate(sample_elements):
                    try:
                        result = ifcopenshell.util.selector.get_element_value(
                            element, partial_path
                        )
                        debug_print(
                            f"Element {i}: extracted {type(result)} from '{partial_path}'"
                        )

                        if result is not None:
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

    def _get_property_set_properties(self, elements: list, pset_name: str) -> Set[str]:
        """Extract actual properties from a specific property set in the elements."""
        debug_print(f"Getting properties for property set: {pset_name}")

        properties = set()

        for element in elements:
            try:
                import ifcopenshell.util.element

                all_psets = ifcopenshell.util.element.get_psets(element)
                debug_print(
                    f"Element #{getattr(element, 'id', lambda: 'Unknown')()} has psets: {list(all_psets.keys())}"
                )

                if pset_name in all_psets:
                    pset_data = all_psets[pset_name]
                    debug_print(
                        f"Found {pset_name} with properties: {list(pset_data.keys())}"
                    )

                    for prop_name in pset_data.keys():
                        if prop_name != "id":
                            properties.add(prop_name)
                            debug_print(f"Added property: {prop_name}")

            except Exception as e:
                debug_print(f"Failed to get property sets for element: {e}")
                continue

        if properties:
            debug_print(
                f"Found {len(properties)} properties in {pset_name}: {sorted(properties)}"
            )
        else:
            debug_print(f"No properties found for {pset_name}")
            if pset_name in self.cache.properties_by_pset:
                cached_props = self.cache.properties_by_pset[pset_name]
                debug_print(f"Using cached properties for {pset_name}: {cached_props}")
                properties.update(cached_props)

        return properties

    def _get_matching_property_set_names(self, elements: list, prefix: str) -> Set[str]:
        """Get property set names that match the given prefix."""
        debug_print(f"Getting property set names matching prefix: '{prefix}'")

        matching_names = set()

        for element in elements:
            try:
                import ifcopenshell.util.element

                all_psets = ifcopenshell.util.element.get_psets(element)
                element_id = getattr(element, "id", lambda: "Unknown")()
                debug_print(f"Element #{element_id} has {len(all_psets)} property sets")

                for pset_name in all_psets.keys():
                    if pset_name.startswith(prefix):
                        matching_names.add(pset_name)
                        debug_print(f"Found matching property set: {pset_name}")

            except Exception as e:
                debug_print(f"Failed to get property sets for element: {e}")
                continue

        debug_print(
            f"Found {len(matching_names)} matching property set names: {sorted(matching_names)}"
        )
        return matching_names

    def _find_complete_property_set_names(
        self, elements: list, prefix: str
    ) -> Set[str]:
        """Find property set names that match the given prefix."""
        debug_print(f"Finding property set names with prefix: {prefix}")

        matching_names = set()

        for element in elements:
            try:
                import ifcopenshell.util.element

                all_psets = ifcopenshell.util.element.get_psets(element)

                for pset_name in all_psets.keys():
                    if pset_name.startswith(prefix):
                        matching_names.add(pset_name)
                        debug_print(f"Found matching property set: {pset_name}")

            except Exception as e:
                debug_print(f"Failed to get property sets for element: {e}")
                continue

        debug_print(f"Found {len(matching_names)} matching property set names")
        return matching_names

    def _inspect_result(self, result: Any) -> Set[str]:
        """Inspect a result object to determine what attributes/indices are available."""
        attributes = set()

        debug_print(f"_inspect_result called with: {type(result)}")

        try:
            if result is None:
                debug_print("Result is None")
                return attributes

            # Handle list/tuple results
            if isinstance(result, (list, tuple)):
                debug_print(f"Detected list/tuple with {len(result)} items")

                attributes.add("count")
                for i in range(min(len(result), 10)):
                    attributes.add(str(i))

                if hasattr(self.cache, "selector_keywords"):
                    attributes.update(self.cache.selector_keywords)

                debug_print(f"List result completions: {sorted(attributes)}")
                return attributes

            # Handle object results
            debug_print(f"Treating as object: {type(result)}")

            entity_attrs = self._get_entity_attributes(result)
            attributes.update(entity_attrs)

            if hasattr(self.cache, "selector_keywords"):
                attributes.update(self.cache.selector_keywords)

        except Exception as e:
            debug_print(f"Error in _inspect_result: {e}")
            if hasattr(self.cache, "selector_keywords"):
                attributes.update(self.cache.selector_keywords)

        debug_print(f"_inspect_result returning: {sorted(attributes)}")
        return attributes

    def _get_entity_attributes(self, entity: Any) -> Set[str]:
        """Get attributes from any entity by direct inspection."""
        attributes = set()

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

        try:
            all_attrs = dir(entity)
            debug_print(f"dir() returned {len(all_attrs)} attributes")

            for attr_name in all_attrs:
                if (
                    attr_name
                    and isinstance(attr_name, str)
                    and len(attr_name) > 0
                    and attr_name[0].isupper()
                    and not attr_name.startswith("_")
                ):
                    try:
                        getattr(entity, attr_name)
                        attributes.add(attr_name)
                    except (AttributeError, TypeError):
                        continue
                    except Exception:
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
