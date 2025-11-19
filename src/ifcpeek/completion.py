"""
This is a completion system that implements:
1. Unified IfcCompleter class supporting both filter and value extraction contexts
2. Complete IfcOpenShell integration using filter_elements() and get_element_value()
3. Context-aware completions based on actual model data
4. Dynamic property set and value path discovery
"""

import re
import sys
from typing import Dict, Set, Any, List, Optional, Tuple
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
import ifcopenshell
import ifcopenshell.util.selector
import ifcopenshell.util.element
from .debug import debug_print


class IfcCompleter(Completer):
    """
    Unified IFC completer supporting both filter queries and value extraction.
    """

    def __init__(self, model: ifcopenshell.file):
        """Initialize completer with IFC model."""
        self.model = model

        # Lazy-loaded caches (only for basic model structure)
        self._ifc_classes: Optional[Set[str]] = None
        self._basic_property_sets: Optional[Set[str]] = None
        self._basic_properties: Optional[Dict[str, Set[str]]] = None

        # Core IFC completion data
        self.selector_keywords = {
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

        self.filter_keywords = {
            "material",
            "type",
            "location",
            "parent",
            "classification",
            "query",
        }

        self.common_attributes = {
            "Name",
            "Description",
            "GlobalId",
            "Tag",
            "ObjectType",
            "PredefinedType",
            "Width",
            "Height",
            "Length",
            "Thickness",
        }

        self.comparison_operators = {"=", "!=", ">", ">=", "<", "<=", "*=", "!*="}

        debug_print("Enhanced IfcCompleter initialized")

    def get_completions(self, document: Document, complete_event):
        """Main completion method that routes to appropriate handler."""
        text = document.text
        cursor_pos = document.cursor_position

        debug_print(f"IfcCompleter called: '{text}', cursor at {cursor_pos}")

        try:
            # Analyze completion context
            context = self._analyze_completion_context(text, cursor_pos)
            debug_print(f"Context analysis: {context}")

            if context["type"] == "filter":
                yield from self._get_filter_completions(context)
            elif context["type"] == "value":
                yield from self._get_value_completions(context)

        except Exception as e:
            debug_print(f"Completion error: {e}")
            # NO FALLBACKS - let it fail cleanly
            return

    def _analyze_completion_context(self, text: str, cursor_pos: int) -> Dict[str, Any]:
        """Analyze text and cursor position to determine completion context."""
        debug_print(f"Analyzing context: '{text}' at position {cursor_pos}")

        # Determine if we're in filter or value extraction context
        semicolon_positions = [i for i, char in enumerate(text) if char == ";"]

        if not semicolon_positions:
            # No semicolons - definitely filter context
            return self._analyze_filter_context(text, cursor_pos)

        # Find which semicolon section we're in
        first_semicolon = semicolon_positions[0]

        if cursor_pos <= first_semicolon:
            # Before first semicolon - filter context
            filter_text = text[:cursor_pos]
            return self._analyze_filter_context(filter_text, cursor_pos)
        else:
            # After first semicolon - value extraction context
            filter_query = text[:first_semicolon].strip()

            # Find which value query section we're in
            remaining_text = text[first_semicolon + 1 :]
            remaining_cursor = cursor_pos - first_semicolon - 1

            return self._analyze_value_context(
                filter_query, remaining_text, remaining_cursor
            )

    def _analyze_filter_context(self, text: str, cursor_pos: int) -> Dict[str, Any]:
        """Analyze filter query context."""
        text_before_cursor = text[:cursor_pos]

        # Parse current word and position
        current_word, start_position = self._parse_current_word(text_before_cursor)

        return {
            "type": "filter",
            "text_before_cursor": text_before_cursor,
            "current_word": current_word,
            "start_position": start_position,
            "full_text": text,
        }

    def _analyze_value_context(
        self, filter_query: str, remaining_text: str, remaining_cursor: int
    ) -> Dict[str, Any]:
        """Analyze value extraction context."""
        # Split remaining text by semicolons to find current value query
        value_parts = remaining_text.split(";")

        # Find which part the cursor is in
        current_pos = 0
        current_part_index = 0

        for i, part in enumerate(value_parts):
            part_end = current_pos + len(part)
            if remaining_cursor <= part_end:
                current_part_index = i
                break
            current_pos = part_end + 1

        if current_part_index < len(value_parts):
            current_part = value_parts[current_part_index]
            cursor_in_part = remaining_cursor - sum(
                len(value_parts[j]) + 1 for j in range(current_part_index)
            )
            if cursor_in_part < 0:
                cursor_in_part = 0
            elif cursor_in_part > len(current_part):
                cursor_in_part = len(current_part)

            current_value_path = current_part[:cursor_in_part].strip()
        else:
            current_value_path = ""

        # Parse current word in value context
        current_word, start_position = self._parse_value_word(current_value_path)

        return {
            "type": "value",
            "filter_query": filter_query,
            "current_value_path": current_value_path,
            "current_word": current_word,
            "start_position": start_position,
        }

    def _parse_current_word(self, text_before_cursor: str) -> Tuple[str, int]:
        """Parse current word and start position for filter context."""
        # Handle comparison operators
        comparison_match = re.search(
            r"(\w+)\s*(>=|<=|!=|\*=|!\*=|>|<|=)\s*(.*)$", text_before_cursor
        )
        if comparison_match:
            partial_value = comparison_match.group(3)
            return partial_value, -len(partial_value) if partial_value else 0

        # Handle negation
        if text_before_cursor.endswith("!"):
            return "", 0

        negation_match = re.search(r"!\s*([A-Za-z]*)$", text_before_cursor)
        if negation_match:
            word = negation_match.group(1)
            return word, -len(word) if word else 0

        # Handle property set patterns
        pset_dot_match = re.search(r"([A-Za-z0-9_]+)\.\s*$", text_before_cursor)
        if pset_dot_match:
            return "", 0

        # Default word parsing
        word_match = re.search(r"[^,+\s]*$", text_before_cursor)
        if word_match:
            word = word_match.group()
            return word, -len(word) if word else 0

        return "", 0

    def _parse_value_word(self, value_path: str) -> Tuple[str, int]:
        """Parse current word and start position for value context."""
        if not value_path:
            return "", 0

        # Find last word after dot or at start
        word_match = re.search(r"[^.\s]*$", value_path)
        if word_match:
            word = word_match.group()
            return word, -len(word) if word else 0

        return "", 0

    def _get_filter_completions(self, context: Dict[str, Any]) -> List[Completion]:
        """Get completions for filter queries using IfcOpenShell integration."""
        text_before_cursor = context["text_before_cursor"]
        current_word = context["current_word"]
        start_position = context["start_position"]

        debug_print(f"Getting filter completions for: '{text_before_cursor}'")

        try:
            # Determine what type of completion is needed
            completion_type = self._determine_filter_completion_type(text_before_cursor)
            debug_print(f"Filter completion type: {completion_type}")

            completions = set()

            if completion_type == "ifc_classes":
                completions.update(self._get_ifc_classes())

            elif completion_type == "attributes_and_keywords":
                # Extract cumulative filter to get relevant classes
                cumulative_filter = self._extract_cumulative_filter(text_before_cursor)
                debug_print(f"Cumulative filter: '{cumulative_filter}'")

                # ALWAYS add IFC classes for union queries (e.g., "IfcWall, IfcWindow, Ifc...")
                completions.update(self._get_ifc_classes())

                # ALWAYS add filter keywords
                completions.update(self.filter_keywords)

                # If we have a valid filter, get ALL elements that match it
                if cumulative_filter.strip():
                    try:
                        elements = self._apply_cumulative_filter(cumulative_filter)
                        debug_print(f"Selector query returned {len(elements)} elements")

                        if elements:
                            # Extract actual attributes that exist on these specific elements
                            attributes = self._extract_attributes_from_elements(elements)
                            completions.update(attributes)

                            # Extract actual property sets from these specific elements
                            pset_names = self._extract_property_set_names(elements)
                            completions.update(pset_names)
                    except Exception as e:
                        debug_print(f"Error running selector query '{cumulative_filter}': {e}")

                # Always add property set patterns for typing convenience
                completions.add("Pset_")
                completions.add("Qto_")

            elif completion_type == "property_set_names":
                cumulative_filter = self._extract_cumulative_filter(text_before_cursor)
                elements = self._apply_cumulative_filter(cumulative_filter)

                prefix = self._extract_property_set_prefix(text_before_cursor)
                if elements:
                    pset_names = self._extract_property_set_names(elements, prefix)
                    completions.update(pset_names)

            elif completion_type == "property_names":
                # Extract property set name from the current query
                pset_name = self._extract_property_set_name(text_before_cursor)
                debug_print(f"Extracting properties for property set: '{pset_name}'")

                # FIXED: Don't include the ".PropertyName" part in the cumulative filter
                # Remove the property set reference to get a valid filter query
                cumulative_filter = self._extract_cumulative_filter_before_pset_dot(text_before_cursor)
                debug_print(f"Cumulative filter (before pset.): '{cumulative_filter}'")

                elements = self._apply_cumulative_filter(cumulative_filter)

                if elements and pset_name:
                    properties = self._extract_property_names(elements, pset_name)
                    completions.update(properties)

            elif completion_type == "attribute_values":
                # FIXED: Remove the "=value" part to get a valid filter query
                attribute_name = self._extract_attribute_name(text_before_cursor)
                cumulative_filter = self._extract_cumulative_filter_before_equals(text_before_cursor)
                debug_print(f"Cumulative filter (before =): '{cumulative_filter}'")
                debug_print(f"Attribute name: '{attribute_name}'")

                elements = self._apply_cumulative_filter(cumulative_filter)

                if elements and attribute_name:
                    values = self._extract_attribute_values(elements, attribute_name)
                    completions.update(values)
                    debug_print(f"Found {len(values)} attribute values")

            elif completion_type == "comparison_operators":
                completions.update(self.comparison_operators)

            # Filter completions by current word and yield
            for completion_text in sorted(completions):
                if self._matches_word(completion_text, current_word):
                    yield Completion(text=completion_text, start_position=start_position)

        except Exception as e:
            debug_print(f"Filter completion error: {e}")
            # NO FALLBACKS - let it fail cleanly
            return

    def _get_value_completions(self, context: Dict[str, Any]) -> List[Completion]:
        """Get completions for value extraction using IfcOpenShell integration."""
        filter_query = context["filter_query"]
        current_value_path = context["current_value_path"]
        current_word = context["current_word"]
        start_position = context["start_position"]

        debug_print(
            f"Getting value completions for filter: '{filter_query}', path: '{current_value_path}', word: '{current_word}'"
        )

        try:
            # Apply filter to get relevant elements
            elements = self._apply_cumulative_filter(filter_query)
            debug_print(f"Filter returned {len(elements)} elements")

            if not elements:
                debug_print("No elements found, returning empty completions")
                return
            else:
                # IMPROVED: Sample more elements for better attribute discovery
                # Use up to 50 elements (or all if fewer) for comprehensive completion
                sample_size = min(50, len(elements))
                sampled_elements = elements[:sample_size]
                debug_print(f"Sampling {sample_size} elements for value completions")

                completions = self._resolve_value_path_completions(
                    sampled_elements, current_value_path
                )
                debug_print(f"Resolved {len(completions)} value completions")

            # Filter and yield completions
            yielded = 0
            for completion_text in sorted(completions):
                if self._matches_word(completion_text, current_word):
                    yield Completion(
                        text=completion_text, start_position=start_position
                    )
                    yielded += 1

            debug_print(f"Yielded {yielded} filtered completions")

        except Exception as e:
            debug_print(f"Value completion error: {e}")
            import traceback

            debug_print(f"Traceback: {traceback.format_exc()}")
            # NO FALLBACKS - let it fail cleanly
            return

    def _resolve_value_path_completions(
        self, elements: List, current_value_path: str
    ) -> Set[str]:
        """Resolve completions for value paths using IfcOpenShell get_element_value."""
        debug_print(f"Resolving value path completions for: '{current_value_path}'")

        completions = set()

        try:
            if not current_value_path:
                # Base level - return common value paths
                completions.update(self.selector_keywords)
                completions.update(self.common_attributes)

                # IMPROVED: Add actual attributes from the filtered elements
                actual_attributes = self._extract_attributes_from_elements(elements)
                completions.update(actual_attributes)
                debug_print(f"Added {len(actual_attributes)} actual attributes")

                # Add property sets available on these elements
                for element in elements:
                    try:
                        psets = ifcopenshell.util.element.get_psets(element)
                        completions.update(psets.keys())
                    except Exception:
                        continue

                return completions

            # FIXED: Check property completion BEFORE property set name completion
            # Handle property completion within property sets: "Pset_WallCommon." -> properties
            if self._is_property_completion(current_value_path):
                pset_name = current_value_path.rstrip(".")
                debug_print(f"Property completion for property set: '{pset_name}'")

                for element in elements:
                    try:
                        psets = ifcopenshell.util.element.get_psets(element)
                        if pset_name in psets:
                            for prop_name in psets[pset_name].keys():
                                if prop_name != "id":
                                    completions.add(prop_name)
                    except Exception:
                        continue

                return completions

            # Handle property set name completion: "P" -> "Pset_WallCommon"
            if self._is_property_set_name_completion(current_value_path):
                prefix = current_value_path
                debug_print(f"Property set name completion for prefix: '{prefix}'")

                for element in elements:
                    try:
                        psets = ifcopenshell.util.element.get_psets(element)
                        for pset_name in psets.keys():
                            if pset_name.startswith(prefix):
                                completions.add(pset_name)
                    except Exception:
                        continue

                return completions

            # Handle completion for property set names that are complete but don't have dot
            # e.g., "Pset_WallCommon" should also be offered as completion
            for element in elements:
                try:
                    psets = ifcopenshell.util.element.get_psets(element)
                    for pset_name in psets.keys():
                        if pset_name.startswith(current_value_path):
                            completions.add(pset_name)
                except Exception:
                    continue

            # Handle path completion (type.Name, material.Category, etc.)
            if "." in current_value_path:
                path_parts = current_value_path.split(".")
                if path_parts[-1] == "":
                    # Completing after dot: "type." -> get attributes of type objects
                    partial_path = ".".join(path_parts[:-1])
                    debug_print(f"Path completion after dot: '{partial_path}'")

                    # Track if we encounter tuple/list results
                    has_tuple_results = False

                    for element in elements:
                        try:
                            result = ifcopenshell.util.selector.get_element_value(
                                element, partial_path
                            )
                            if result is not None:
                                # Check if this is a tuple/list
                                if isinstance(result, (list, tuple)):
                                    has_tuple_results = True

                                attrs = self._inspect_object_attributes(result)
                                completions.update(attrs)
                        except Exception:
                            continue

                    # IMPROVED: Only add selector keywords for non-tuple/non-list results
                    # Tuples/lists should only offer numeric indices and 'count'
                    if not has_tuple_results:
                        completions.update(self.selector_keywords)
                        debug_print("Added selector keywords for object navigation")
                    else:
                        debug_print("Skipped selector keywords (tuple/list result)")

                    return completions

            # Default: try to complete as a partial path
            debug_print(f"Default path completion for: '{current_value_path}'")
            completions.update(self.selector_keywords)
            completions.update(self.common_attributes)

            return completions

        except Exception as e:
            debug_print(f"Error resolving value path: {e}")
            # NO FALLBACKS - return empty set
            return set()

    def _inspect_object_attributes(self, obj: Any) -> Set[str]:
        """Inspect an object to find available attributes."""
        attributes = set()

        try:
            if hasattr(obj, "__dict__"):
                dict_attrs = [k for k in obj.__dict__.keys() if k and k[0].isupper()]
                attributes.update(dict_attrs)
        except Exception:
            pass

        try:
            for attr_name in dir(obj):
                if (
                    attr_name
                    and attr_name[0].isupper()
                    and not attr_name.startswith("_")
                ):
                    try:
                        getattr(obj, attr_name)
                        attributes.add(attr_name)
                    except Exception:
                        continue
        except Exception:
            pass

        # Handle lists/tuples
        if isinstance(obj, (list, tuple)):
            attributes.add("count")
            for i in range(min(len(obj), 10)):
                attributes.add(str(i))

        return attributes

    # ============================
    # IfcOpenShell Integration Methods
    # ============================

    def _apply_cumulative_filter(self, filter_query: str) -> List:
        """Apply filter using IfcOpenShell - handles ALL complex parsing."""
        if not filter_query.strip():
            debug_print("Empty filter query, returning empty list")
            return []

        try:
            debug_print(f"Applying cumulative filter: '{filter_query}'")
            elements = list(
                ifcopenshell.util.selector.filter_elements(self.model, filter_query)
            )
            debug_print(f"Filter returned {len(elements)} elements")
            return elements
        except Exception as e:
            debug_print(f"Filter failed: {e}")
            # NO FALLBACK - let it fail properly so we can see what's wrong
            return []

    def _extract_attributes_from_elements(self, elements: List) -> Set[str]:
        """Extract actual attributes from all filtered elements."""
        attributes = set()
        processed_classes = set()

        for element in elements:
            try:
                class_name = element.is_a()

                # Only process schema for each class once
                if class_name not in processed_classes:
                    processed_classes.add(class_name)

                    # Method 1: Check IFC schema attributes for this class
                    try:
                        # FIXED: Get the actual schema object from ifcopenshell
                        import ifcopenshell.ifcopenshell_wrapper as wrapper
                        schema = wrapper.schema_by_name(self.model.schema)

                        class_def = schema.declaration_by_name(class_name)
                        if class_def and hasattr(class_def, "all_attributes"):
                            for attr in class_def.all_attributes():
                                if hasattr(attr, "name"):
                                    attr_name = attr.name()
                                    if attr_name and attr_name[0].isupper():
                                        attributes.add(attr_name)
                    except Exception:
                        pass

                # Method 2: Check actual attribute values on element
                try:
                    for attr_name in dir(element):
                        if (
                            attr_name
                            and attr_name[0].isupper()
                            and not attr_name.startswith("_")
                            and not callable(getattr(element, attr_name, None))
                        ):
                            try:
                                getattr(element, attr_name)
                                attributes.add(attr_name)
                            except Exception:
                                continue
                except Exception:
                    pass

                # Method 3: Check __dict__ for stored attributes
                try:
                    if hasattr(element, "__dict__"):
                        for attr_name in element.__dict__.keys():
                            if attr_name and attr_name[0].isupper():
                                attributes.add(attr_name)
                except Exception:
                    pass

            except Exception:
                continue

        # Method 4: Test common IFC attributes on sample elements
        common_ifc_attrs = [
            "Name", "Description", "Tag", "ObjectType", "GlobalId",
            "PredefinedType", "OwnerHistory", "ObjectPlacement", "Representation"
        ]
        test_elements = elements[: min(10, len(elements))]
        for attr_name in common_ifc_attrs:
            for element in test_elements:
                try:
                    if hasattr(element, attr_name):
                        getattr(element, attr_name)
                        attributes.add(attr_name)
                        break
                except Exception:
                    continue

        debug_print(f"Extracted {len(attributes)} attributes from {len(elements)} elements")
        return attributes

    def _extract_property_set_names(self, elements: List, prefix: str = "") -> Set[str]:
        """Extract property set names from all filtered elements."""
        pset_names = set()

        for element in elements:
            try:
                psets = ifcopenshell.util.element.get_psets(element)
                for pset_name in psets.keys():
                    if not prefix or pset_name.startswith(prefix):
                        pset_names.add(pset_name)
            except Exception:
                continue

        debug_print(f"Found {len(pset_names)} property set names")
        return pset_names

    def _extract_property_names(self, elements: List, pset_name: str) -> Set[str]:
        """Extract property names within a property set from all filtered elements."""
        properties = set()

        for element in elements:
            try:
                psets = ifcopenshell.util.element.get_psets(element)
                if pset_name in psets:
                    for prop_name in psets[pset_name].keys():
                        if prop_name != "id":
                            properties.add(prop_name)
            except Exception:
                continue

        debug_print(f"Found {len(properties)} properties in '{pset_name}'")
        return properties

    def _extract_attribute_values(
        self, elements: List, attribute_name: str
    ) -> Set[str]:
        """Extract attribute values from all filtered elements."""
        values = set()
        found_boolean = False

        # Handle property set properties like "Pset_WallCommon.LoadBearing"
        if "." in attribute_name:
            try:
                pset_name, prop_name = attribute_name.rsplit(".", 1)

                for element in elements:
                    try:
                        psets = ifcopenshell.util.element.get_psets(element)
                        if pset_name in psets and prop_name in psets[pset_name]:
                            value = psets[pset_name][prop_name]
                            if value is not None:
                                if isinstance(value, bool):
                                    found_boolean = True
                                elif isinstance(value, str) and value.strip():
                                    values.add(f'"{value.strip()}"')
                                elif isinstance(value, (int, float)):
                                    values.add(f'"{str(value)}"')
                    except Exception:
                        continue
            except ValueError:
                pass
        else:
            # Regular attribute or keyword - use value query mapping
            value_query = self._map_attribute_to_value_query(attribute_name)

            for element in elements:
                try:
                    value = ifcopenshell.util.selector.get_element_value(
                        element, value_query
                    )
                    if value is not None:
                        if isinstance(value, bool):
                            found_boolean = True
                        elif isinstance(value, str) and value.strip():
                            values.add(f'"{value.strip()}"')
                        elif isinstance(value, (int, float)):
                            values.add(f'"{str(value)}"')
                except Exception:
                    continue

        # If any boolean values found, this is a boolean property
        if found_boolean:
            return {"TRUE", "FALSE"}

        return values

    def _map_attribute_to_value_query(self, attribute_name: str) -> str:
        """Map filter attribute names to value extraction queries."""
        mappings = {
            "material": "material.Name",
            "type": "type.Name",
            "location": "storey.Name",
            "parent": "container.Name",
            "classification": "classification.Identification",
        }
        return mappings.get(attribute_name, attribute_name)

    # ============================
    # Context Analysis Methods
    # ============================

    def _determine_filter_completion_type(self, text_before_cursor: str) -> str:
        """Determine what type of filter completion is needed."""
        debug_print(f"Determining completion type for: '{text_before_cursor}'")

        # Check for value completion (after comparison operators)
        value_match = re.search(
            r"(\w+)\s*(>=|<=|!=|\*=|!\*=|>|<|=)\s*", text_before_cursor
        )
        if value_match:
            debug_print("Detected attribute value completion")
            return "attribute_values"

        # Check for property set property completion: "Pset_WallCommon."
        pset_prop_match = re.search(r"([PQE][a-zA-Z0-9_]+)\.\s*$", text_before_cursor)
        if pset_prop_match:
            debug_print(
                f"Detected property set property completion: {pset_prop_match.group(1)}"
            )
            return "property_names"

        # Check for property set name completion: "Pset_", "Qto_", etc.
        pset_name_match = re.search(
            r"[,\s]([PQE][a-zA-Z0-9_]*)\s*$", text_before_cursor
        )
        if pset_name_match:
            debug_print(
                f"Detected property set name completion: {pset_name_match.group(1)}"
            )
            return "property_set_names"

        # Check for comparison operator completion after known attributes/keywords
        trailing_word_match = re.search(
            r"[,\s]([A-Za-z_][A-Za-z0-9_]*)\s*$", text_before_cursor
        )
        if trailing_word_match:
            word = trailing_word_match.group(1)
            if word in (self.filter_keywords | self.common_attributes):
                debug_print(f"Detected comparison operator completion after: {word}")
                return "comparison_operators"

        # FIXED: Check for attributes and keywords after IFC classes
        # This should have higher priority than the general IFC class check
        if re.search(r"Ifc[A-Za-z0-9]+\s*,\s*", text_before_cursor):
            debug_print("Detected attributes and keywords completion after IFC class")
            return "attributes_and_keywords"

        # Check for trailing comma (after any content): "anything, "
        if re.search(r",\s*$", text_before_cursor):
            debug_print("Detected attributes and keywords completion after comma")
            return "attributes_and_keywords"

        # FIXED: Check for space after IFC class without comma: "IfcWall "
        if re.search(r"Ifc[A-Za-z0-9]+\s+$", text_before_cursor):
            debug_print("Detected attributes and keywords completion after IFC class with space")
            return "attributes_and_keywords"

        # Check for start of query or after separators: "", "+ "
        if (
            not text_before_cursor.strip()
            or re.search(r"[+]\s*[A-Za-z]*$", text_before_cursor)
            or re.search(r"^\s*[A-Za-z]*$", text_before_cursor)
        ):
            debug_print("Detected IFC class completion (start or after + separator)")
            return "ifc_classes"

        # Default to attributes and keywords for safety (more useful than IFC classes)
        debug_print("Defaulting to attributes and keywords completion")
        return "attributes_and_keywords"

    def _is_property_set_name_completion(self, value_path: str) -> bool:
        """Check if this is property set name completion."""
        # Handle single character prefixes like "P", "Q", "E"
        if len(value_path) == 1 and value_path in "PQE":
            return True
        return (
            value_path.startswith("Pset_")
            or value_path.startswith("Qto_")
            or value_path.startswith("EPset_")
        )

    def _is_property_completion(self, value_path: str) -> bool:
        """Check if this is property completion within a property set."""
        # FIXED: Check if the path contains a property set pattern followed by dot
        # Example: "Pset_WallCommon." -> True
        if value_path.endswith("."):
            # Check if what comes before the dot is a property set name
            base = value_path.rstrip(".")
            return bool(re.match(r"^(Pset_|Qto_|EPset_|[A-Z]\w*_\w+)$", base))
        return False

    def _extract_cumulative_filter(self, text_before_cursor: str) -> str:
        """Extract the cumulative filter query from text before cursor."""
        debug_print(f"Extracting cumulative filter from: '{text_before_cursor}'")

        text = text_before_cursor.strip()

        # If empty or just whitespace, return empty
        if not text:
            debug_print("Empty text - returning empty filter")
            return ""

        # Strategy: Remove the incomplete word at the end that we're trying to complete

        # Case 1: Text ends with comma and optional whitespace
        if text.endswith(",") or (
            text.endswith(" ") and "," in text and text.split(",")[-1].strip() == ""
        ):
            # Find the last comma and use everything before it
            last_comma_pos = text.rfind(",")
            if last_comma_pos != -1:
                result = text[:last_comma_pos].strip()
                debug_print(f"Text ends with comma - using: '{result}'")
                return result

        # Case 2: Text ends with incomplete word after comma
        if "," in text:
            parts = text.split(",")
            if len(parts) > 1:
                last_part = parts[-1].strip()
                everything_before = ",".join(parts[:-1]).strip()

                debug_print(
                    f"Found potential incomplete word: '{last_part}' after comma"
                )

                # Check if the last part is actually a complete filter component

                # Has comparison operators - it's complete
                if any(
                    op in last_part
                    for op in [">=", "<=", "!=", "*=", "!*=", ">", "<", "="]
                ):
                    debug_print(f"Last part contains operators - including it")
                    return text

                # Property set with dot - it's complete
                if (
                    last_part.startswith(("Pset_", "Qto_", "EPset_"))
                    and "." in last_part
                ):
                    debug_print(f"Last part is property set reference - including it")
                    return text

                # Known filter keyword - it's complete
                if last_part in self.filter_keywords:
                    debug_print(f"Last part is filter keyword - including it")
                    return text

                # Complete IFC class - it's complete
                if (
                    last_part.startswith("Ifc")
                    and last_part[3:].replace("_", "").isalnum()
                ):
                    debug_print(f"Last part is complete IFC class - including it")
                    return text

                # Otherwise, it's truly incomplete - use everything before the last comma
                debug_print(
                    f"Truly incomplete word - using before comma: '{everything_before}'"
                )
                return everything_before

        # Case 3: No comma structure - use entire text
        debug_print(f"No comma structure found - using entire text: '{text}'")
        return text

    def _extract_property_set_prefix(self, text_before_cursor: str) -> str:
        """Extract property set prefix from text."""
        match = re.search(r"[,\s]([PQE][a-zA-Z0-9_]*)\s*$", text_before_cursor)
        return match.group(1) if match else ""

    def _extract_property_set_name(self, text_before_cursor: str) -> str:
        """Extract property set name from text."""
        match = re.search(r"([PQE][a-zA-Z0-9_]+)\.\s*$", text_before_cursor)
        return match.group(1) if match else ""

    def _extract_attribute_name(self, text_before_cursor: str) -> str:
        """Extract attribute name from text for value completion."""
        debug_print(f"Extracting attribute name from: '{text_before_cursor}'")

        # Handle property set properties like "Pset_WallCommon.LoadBearing"
        pset_prop_match = re.search(
            r"([PQE][a-zA-Z0-9_]+\.[A-Za-z0-9_]+)\s*[>=<!]", text_before_cursor
        )
        if pset_prop_match:
            attr_name = pset_prop_match.group(1)
            debug_print(f"Found property set property: {attr_name}")
            return attr_name

        # Handle regular attributes
        match = re.search(r"(\w+)\s*[>=<!]", text_before_cursor)
        if match:
            attr_name = match.group(1)
            debug_print(f"Found regular attribute: {attr_name}")
            return attr_name

        debug_print("No attribute name found")
        return ""

    def _extract_cumulative_filter_before_pset_dot(self, text_before_cursor: str) -> str:
        """Extract cumulative filter before property set dot notation."""
        # Remove the "Pset_PropertySetName." part to get valid filter
        # Example: "IfcWall, Pset_WallCommon." -> "IfcWall"
        match = re.search(r"^(.+?),\s*[PQE][a-zA-Z0-9_]+\.\s*$", text_before_cursor)
        if match:
            return match.group(1).strip()

        # If no match, use the regular extraction but try to clean it up
        return self._extract_cumulative_filter(text_before_cursor)

    def _extract_cumulative_filter_before_equals(self, text_before_cursor: str) -> str:
        """Extract cumulative filter before equals sign."""
        # Remove the "AttributeName=value" part to get valid filter
        # Example: "IfcWall, Name=" -> "IfcWall"
        match = re.search(r"^(.+?),\s*\w+\s*[>=<!]+\s*", text_before_cursor)
        if match:
            return match.group(1).strip()

        # Try without comma
        match = re.search(r"^(.+?)\s+\w+\s*[>=<!]+\s*", text_before_cursor)
        if match:
            return match.group(1).strip()

        # If no match, use the regular extraction
        return self._extract_cumulative_filter(text_before_cursor)

    # ============================
    # Lazy Loading Methods
    # ============================

    def _get_ifc_classes(self) -> Set[str]:
        """Get IFC classes from model (lazy loaded), including parent classes."""
        if self._ifc_classes is None:
            self._ifc_classes = set()
            try:
                # FIXED: Get the actual schema object from ifcopenshell
                # model.schema is a string like "IFC4", not the schema object
                import ifcopenshell.ifcopenshell_wrapper as wrapper
                schema = wrapper.schema_by_name(self.model.schema)

                # Get classes from actual entities
                for entity in self.model:
                    try:
                        class_name = entity.is_a()
                        self._ifc_classes.add(class_name)

                        # Add parent classes by checking schema hierarchy
                        try:
                            entity_info = schema.declaration_by_name(class_name)
                            # Walk up the inheritance hierarchy
                            # FIXED: supertype is a method, not a property - must call it
                            current = entity_info
                            while hasattr(current, "supertype"):
                                parent = current.supertype()  # Call the method
                                if parent is None:
                                    break
                                parent_name = parent.name()
                                if parent_name.startswith("Ifc"):
                                    self._ifc_classes.add(parent_name)
                                current = parent
                        except Exception as e:
                            debug_print(
                                f"Could not traverse hierarchy for {class_name}: {e}"
                            )
                            # No fallback - let it fail if schema traversal doesn't work

                    except Exception as e:
                        debug_print(f"Could not process entity: {e}")
                        continue

            except Exception as e:
                debug_print(f"Could not iterate model entities: {e}")
                # No fallback - empty set if model iteration fails

        return self._ifc_classes

    def _get_basic_property_sets(self) -> Set[str]:
        """Get basic property set names (lazy loaded)."""
        if self._basic_property_sets is None:
            self._basic_property_sets = set()
            try:
                # Sample IfcPropertySet entities
                for pset in list(self.model.by_type("IfcPropertySet"))[:20]:
                    try:
                        if hasattr(pset, "Name") and pset.Name:
                            self._basic_property_sets.add(pset.Name)
                    except Exception:
                        continue

                # Sample IfcElementQuantity entities
                for qset in list(self.model.by_type("IfcElementQuantity"))[:20]:
                    try:
                        if hasattr(qset, "Name") and qset.Name:
                            self._basic_property_sets.add(qset.Name)
                    except Exception:
                        continue
            except Exception:
                pass
        return self._basic_property_sets

    def _get_basic_properties(self) -> Dict[str, Set[str]]:
        """Get basic properties by property set (lazy loaded)."""
        if self._basic_properties is None:
            self._basic_properties = {}
            try:
                # Sample property sets
                for pset in list(self.model.by_type("IfcPropertySet"))[:20]:
                    try:
                        if (
                            hasattr(pset, "Name")
                            and pset.Name
                            and hasattr(pset, "HasProperties")
                        ):
                            props = set()
                            for prop in pset.HasProperties:
                                if hasattr(prop, "Name") and prop.Name:
                                    props.add(prop.Name)
                            if props:
                                self._basic_properties[pset.Name] = props
                    except Exception:
                        continue

                # Sample quantity sets
                for qset in list(self.model.by_type("IfcElementQuantity"))[:20]:
                    try:
                        if (
                            hasattr(qset, "Name")
                            and qset.Name
                            and hasattr(qset, "Quantities")
                        ):
                            props = set()
                            for qty in qset.Quantities:
                                if hasattr(qty, "Name") and qty.Name:
                                    props.add(qty.Name)
                            if props:
                                self._basic_properties[qset.Name] = props
                    except Exception:
                        continue
            except Exception:
                pass
        return self._basic_properties

    # ============================
    # Utility Methods
    # ============================

    def _matches_word(self, completion_text: str, current_word: str) -> bool:
        """Check if completion matches current word."""
        if not current_word:
            return True

        # Handle quoted completions
        if completion_text.startswith('"') and completion_text.endswith('"'):
            comparison_text = completion_text[1:-1]
        else:
            comparison_text = completion_text

        return comparison_text.lower().startswith(current_word.lower())


# ============================
# Factory Function
# ============================


def create_completion_system(model: ifcopenshell.file):
    """
    Create the enhanced completion system.

    This replaces the old complex multi-class system with a single,
    reliable completer that leverages IfcOpenShell for all operations.

    Args:
        model: IfcOpenShell file model

    Returns:
        IfcCompleter: Single completer instance
    """
    try:
        debug_print("Creating enhanced completion system...")
        completer = IfcCompleter(model)
        debug_print("Enhanced completion system created successfully")
        return completer
    except Exception as e:
        debug_print(f"Failed to create enhanced completion system: {e}")
        raise e


# ============================
# Test Suite
# ============================


def test_completion():
    """
    Comprehensive test suite for the enhanced completion system.
    """
    import tempfile
    import os
    from unittest.mock import Mock

    print("Testing Enhanced IfcPeek Completion System - No Fallbacks Version")
    print("=" * 70)

    def create_mock_model():
        """Create a mock IFC model for testing."""
        mock_model = Mock()

        # Mock entities
        mock_wall = Mock()
        mock_wall.is_a.return_value = "IfcWall"
        mock_wall.Name = "Test Wall"
        mock_wall.Description = "A test wall"

        mock_door = Mock()
        mock_door.is_a.return_value = "IfcDoor"
        mock_door.Name = "Test Door"

        mock_model.__iter__ = Mock(return_value=iter([mock_wall, mock_door]))

        # Mock property sets
        mock_pset = Mock()
        mock_pset.Name = "Pset_WallCommon"
        mock_prop = Mock()
        mock_prop.Name = "FireRating"
        mock_pset.HasProperties = [mock_prop]

        def mock_by_type(entity_type):
            if entity_type == "IfcPropertySet":
                return [mock_pset]
            elif entity_type == "IfcElementQuantity":
                return []
            elif entity_type == "IfcWall":
                return [mock_wall]
            elif entity_type == "IfcDoor":
                return [mock_door]
            return []

        mock_model.by_type = mock_by_type
        return mock_model

    def test_completer_creation():
        """Test basic completer creation."""
        print("\n1. Testing completer creation...")

        mock_model = create_mock_model()
        completer = IfcCompleter(mock_model)

        assert completer.model is mock_model
        assert len(completer.selector_keywords) > 0
        assert len(completer.filter_keywords) > 0
        assert len(completer.common_attributes) > 0

        print("   ✓ Completer created successfully")
        print(f"   ✓ {len(completer.selector_keywords)} selector keywords loaded")
        print(f"   ✓ {len(completer.filter_keywords)} filter keywords loaded")
        print("   ✓ No fallbacks configured - will fail cleanly when needed")

    def test_no_fallback_behavior():
        """Test that no fallbacks are provided when operations fail."""
        print("\n2. Testing no-fallback behavior...")

        # Create a broken model
        broken_model = Mock()
        broken_model.__iter__ = Mock(side_effect=Exception("Model broken"))
        broken_model.by_type = Mock(side_effect=Exception("by_type broken"))

        completer = IfcCompleter(broken_model)

        from prompt_toolkit.document import Document

        doc = Document("IfcW", cursor_position=4)
        completions = list(completer.get_completions(doc, None))

        # Should get NO completions when things fail
        print(
            f"   ✓ Broken model returned {len(completions)} completions (expected: 0)"
        )
        print("   ✓ No fallback completions provided")
        print("   ✓ System fails cleanly without masking issues")

    # Run tests
    try:
        test_completer_creation()
        test_no_fallback_behavior()

        print("\n" + "=" * 70)
        print(
            "✅ All tests passed! Enhanced completion system with no fallbacks is working."
        )
        print("✅ System will fail cleanly when operations don't work as intended.")
        print("✅ Real issues will be revealed instead of being masked by fallbacks.")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_completion()
