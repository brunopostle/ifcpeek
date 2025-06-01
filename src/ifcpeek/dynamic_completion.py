"""
Dynamic completion system that inspects actual IFC entities.
Save this as: ifcpeek/dynamic_completion.py
"""

import re
import sys
from typing import Dict, Set, Any
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
import ifcopenshell
import ifcopenshell.util.selector


class DynamicIfcCompletionCache:
    """Cache with dynamic entity inspection for accurate completions."""

    def __init__(self, model: ifcopenshell.file):
        self.model = model
        self.ifc_classes_in_model: Set[str] = set()
        self.property_sets: Set[str] = set()
        self.properties_by_pset: Dict[str, Set[str]] = {}
        self.schema_cache: Dict[str, Set[str]] = {}

        # Core selector keywords
        self.selector_keywords: Set[str] = {
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

        self._build_cache()

    def _build_cache(self):
        """Build cache of IFC classes and property sets from the model."""
        print("Building dynamic completion cache...", file=sys.stderr)

        # Cache IFC classes in the model
        print("- Scanning IFC classes", file=sys.stderr)
        for entity in self.model:
            class_name = entity.is_a()
            self.ifc_classes_in_model.add(class_name)

        # Cache property sets
        print("- Scanning property sets", file=sys.stderr)
        self._cache_property_sets()

        cache_info = f"Dynamic cache ready: {len(self.ifc_classes_in_model)} classes, {len(self.property_sets)} property sets"
        print(cache_info, file=sys.stderr)

    def _cache_property_sets(self):
        """Cache property sets and their properties from the model."""
        try:
            for pset in self.model.by_type("IfcPropertySet"):
                if hasattr(pset, "Name") and pset.Name:
                    pset_name = pset.Name
                    self.property_sets.add(pset_name)

                    properties = set()
                    if hasattr(pset, "HasProperties") and pset.HasProperties:
                        for prop in pset.HasProperties:
                            if hasattr(prop, "Name") and prop.Name:
                                properties.add(prop.Name)

                    self.properties_by_pset[pset_name] = properties
        except Exception as e:
            print(f"Warning: Could not cache IfcPropertySet: {e}", file=sys.stderr)

        try:
            for qset in self.model.by_type("IfcElementQuantity"):
                if hasattr(qset, "Name") and qset.Name:
                    qset_name = qset.Name
                    self.property_sets.add(qset_name)

                    properties = set()
                    if hasattr(qset, "Quantities") and qset.Quantities:
                        for qty in qset.Quantities:
                            if hasattr(qty, "Name") and qty.Name:
                                properties.add(qty.Name)

                    self.properties_by_pset[qset_name] = properties
        except Exception as e:
            print(f"Warning: Could not cache IfcElementQuantity: {e}", file=sys.stderr)

    def extract_ifc_classes_from_query(self, filter_query: str) -> Set[str]:
        """Extract IFC class names from a filter query."""
        if not filter_query.strip():
            return self.ifc_classes_in_model

        classes = set()
        # Split by commas and plus signs
        query_parts = re.split(r"[,+]", filter_query)

        for part in query_parts:
            part = part.strip()
            # Find IFC class names (starting with Ifc)
            pattern = r"\bIfc[A-Za-z0-9]*\b"
            ifc_classes = re.findall(pattern, part)
            for ifc_class in ifc_classes:
                if ifc_class in self.ifc_classes_in_model:
                    classes.add(ifc_class)

        return classes if classes else self.ifc_classes_in_model


class DynamicContextResolver:
    """Resolves completions by executing value paths and inspecting results."""

    def __init__(self, cache: DynamicIfcCompletionCache):
        self.cache = cache

    def get_completions_for_path(self, filter_query: str, value_path: str) -> Set[str]:
        """Get completions by executing the path and inspecting actual results."""
        try:
            # Execute the filter to get sample elements
            elements = ifcopenshell.util.selector.filter_elements(
                self.cache.model, filter_query
            )
            if not elements:
                return self._get_fallback_completions()

            # Convert set to list and take samples
            element_list = list(elements)
            sample_elements = element_list[: min(10, len(element_list))]

            all_attributes = set()
            path_parts = value_path.split(".")

            if len(path_parts) <= 1:
                # Root level - inspect the filter result elements themselves
                for element in sample_elements:
                    attrs = self._get_entity_attributes(element)
                    all_attributes.update(attrs)

                # Add selector keywords and property sets
                all_attributes.update(self.cache.selector_keywords)
                all_attributes.update(self.cache.property_sets)
                all_attributes.add("/Pset_.*Common/")
                all_attributes.add("/Qto_.*/")

                return all_attributes

            # Execute path up to the second-to-last component
            partial_path = ".".join(path_parts[:-1])

            # Collect results from all samples
            all_results = []
            for element in sample_elements:
                try:
                    result = ifcopenshell.util.selector.get_element_value(
                        element, partial_path
                    )
                    if result is not None:
                        all_results.append(result)
                except Exception:
                    continue

            # Process all results to get comprehensive attributes
            for result in all_results:
                attrs = self._inspect_result(result)
                all_attributes.update(attrs)

            # Special handling for lists - find the maximum list size
            list_sizes = []
            for result in all_results:
                if isinstance(result, (list, tuple)):
                    list_sizes.append(len(result))

            if list_sizes:
                max_list_size = max(list_sizes)
                # Add indices for the largest list found
                for i in range(max_list_size):
                    all_attributes.add(str(i))

            if not all_attributes:
                return self._get_fallback_completions()

            return all_attributes

        except Exception as e:
            print(f"Error in completion: {e}", file=sys.stderr)
            return self._get_fallback_completions()

    def _inspect_result(self, result: Any) -> Set[str]:
        """Inspect a result object to determine what attributes are available."""
        attributes = set()

        try:
            if result is None:
                return attributes

            # Handle lists/tuples
            if isinstance(result, (list, tuple)):
                attributes.add("count")
                if result:
                    # Add indices based on the actual length
                    for i in range(len(result)):
                        attributes.add(str(i))

                # IMPORTANT: Also add selector keywords for lists
                # Lists can still use .class, .id, etc.
                attributes.update(self.cache.selector_keywords)
                return attributes

            # Handle IFC entities or other objects
            attributes = self._get_entity_attributes(result)

            # Always add selector keywords for any object
            attributes.update(self.cache.selector_keywords)

        except Exception:
            pass

        return attributes

    def _get_entity_attributes(self, entity: Any) -> Set[str]:
        """Get attributes from any entity by direct inspection."""
        attributes = set()

        try:
            # Method 1: __dict__ keys (most direct)
            if hasattr(entity, "__dict__"):
                dict_keys = list(entity.__dict__.keys())
                # Filter for IFC attributes (uppercase)
                dict_attrs = [k for k in dict_keys if k[0].isupper()]
                attributes.update(dict_attrs)

            # Method 2: dir() filtering for additional attributes
            for attr_name in dir(entity):
                if attr_name[0].isupper() and not attr_name.startswith("_"):
                    # Quick test that it's actually accessible
                    try:
                        getattr(entity, attr_name)
                        attributes.add(attr_name)
                    except:
                        pass

        except Exception as e:
            print(f"Error inspecting entity: {e}", file=sys.stderr)

        return attributes

    def _get_fallback_completions(self) -> Set[str]:
        """Get fallback completions when dynamic inspection fails."""
        fallback = set()
        fallback.update(self.cache.selector_keywords)
        fallback.update(["Name", "Description", "GlobalId", "class", "id"])
        fallback.update(self.cache.property_sets)
        return fallback


class DynamicIfcValueCompleter(Completer):
    """Context-aware tab completer using dynamic entity inspection."""

    def __init__(self, cache: DynamicIfcCompletionCache):
        self.cache = cache
        self.resolver = DynamicContextResolver(cache)

    def get_completions(self, document: Document, complete_event):
        """Generate completions for the current cursor position."""
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
            "cached_schema_attributes": len(self.cache.schema_cache),
            "property_sets": len(self.cache.property_sets),
            "selector_keywords": len(self.cache.selector_keywords),
            "sample_classes": sorted(list(self.cache.ifc_classes_in_model)[:10]),
            "sample_property_sets": sorted(list(self.cache.property_sets)[:10]),
        }


def create_dynamic_completion_system(model: ifcopenshell.file):
    """Create the dynamic completion system."""
    cache = DynamicIfcCompletionCache(model)
    completer = DynamicIfcValueCompleter(cache)
    return cache, completer
