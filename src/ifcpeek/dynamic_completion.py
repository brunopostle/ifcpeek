"""
Enhanced dynamic completion system with both filter and value extraction support.
This replaces the original dynamic_completion.py with comprehensive functionality.
Save this as: ifcpeek/dynamic_completion.py (replacing the existing file)
"""

import re
import sys
from typing import Dict, Set, Any
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
import ifcopenshell
import ifcopenshell.util.selector


class DynamicIfcCompletionCache:
    """Enhanced cache with both filter and value extraction completion support."""

    def __init__(self, model: ifcopenshell.file):
        self.model = model
        self.ifc_classes_in_model: Set[str] = set()
        self.property_sets: Set[str] = set()
        self.properties_by_pset: Dict[str, Set[str]] = {}
        self.schema_cache: Dict[str, Set[str]] = {}
        self.attribute_cache: Dict[str, Set[str]] = {}

        # Core selector keywords for value extraction
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

        # Filter syntax keywords for selector queries
        self.filter_keywords: Set[str] = {
            "material",
            "type",
            "location",
            "parent",
            "classification",
            "query",
        }

        # Common IFC attributes that can be used in filters
        self.common_attributes: Set[str] = {
            "Name",
            "Description",
            "GlobalId",
            "OwnerHistory",
            "ObjectType",
            "ObjectPlacement",
            "Representation",
            "Tag",
            "PredefinedType",
        }

        # Comparison operators
        self.comparison_operators: Set[str] = {
            "=",
            "!=",
            ">",
            ">=",
            "<",
            "<=",
            "*=",
            "!*=",
        }

        self._build_cache()

    def _build_cache(self):
        """Build comprehensive cache for both filter and value completion."""
        print("Building enhanced completion cache...", file=sys.stderr)

        # Cache IFC classes in the model
        print("- Scanning IFC classes", file=sys.stderr)
        for entity in self.model:
            class_name = entity.is_a()
            self.ifc_classes_in_model.add(class_name)

        # Cache property sets and attributes
        print("- Scanning property sets and attributes", file=sys.stderr)
        self._cache_property_sets()
        self._cache_entity_attributes()

        cache_info = (
            f"Enhanced cache ready: {len(self.ifc_classes_in_model)} classes, "
            f"{len(self.property_sets)} property sets, "
            f"{len(self.attribute_cache)} classes with cached attributes"
        )
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

    def _cache_entity_attributes(self):
        """Cache attributes for each IFC class by sampling entities."""
        print("- Caching entity attributes", file=sys.stderr)

        # Sample a few entities from each class to get their attributes
        class_samples = {}
        for entity in self.model:
            class_name = entity.is_a()
            if class_name not in class_samples:
                class_samples[class_name] = []
            if len(class_samples[class_name]) < 3:  # Sample up to 3 entities per class
                class_samples[class_name].append(entity)

        # Extract attributes from samples
        for class_name, entities in class_samples.items():
            attributes = set()
            attributes.update(
                self.common_attributes
            )  # Always include common attributes

            for entity in entities:
                entity_attrs = self._get_entity_attributes(entity)
                attributes.update(entity_attrs)

            self.attribute_cache[class_name] = attributes

    def _get_entity_attributes(self, entity: Any) -> Set[str]:
        """Get attributes from any entity by direct inspection."""
        attributes = set()

        try:
            # Method 1: __dict__ keys (most direct)
            if hasattr(entity, "__dict__"):
                dict_keys = list(entity.__dict__.keys())
                # Filter for IFC attributes (uppercase)
                dict_attrs = [k for k in dict_keys if k and k[0].isupper()]
                attributes.update(dict_attrs)

            # Method 2: dir() filtering for additional attributes
            for attr_name in dir(entity):
                if (
                    attr_name
                    and attr_name[0].isupper()
                    and not attr_name.startswith("_")
                ):
                    # Quick test that it's actually accessible
                    try:
                        getattr(entity, attr_name)
                        attributes.add(attr_name)
                    except:
                        pass

        except Exception as e:
            print(f"Error inspecting entity: {e}", file=sys.stderr)

        return attributes

    def extract_ifc_classes_from_query(self, filter_query: str) -> Set[str]:
        """Extract IFC class names from a filter query."""
        if not filter_query.strip():
            return self.ifc_classes_in_model

        classes = set()
        # Split by commas and plus signs, but be careful with complex expressions
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

    def get_attributes_for_classes(self, classes: Set[str]) -> Set[str]:
        """Get all available attributes for given IFC classes."""
        all_attributes = set()

        for class_name in classes:
            if class_name in self.attribute_cache:
                all_attributes.update(self.attribute_cache[class_name])
            else:
                # Fallback to common attributes if class not cached
                all_attributes.update(self.common_attributes)

        return all_attributes


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


class FilterQueryCompleter(Completer):
    """Tab completer for IFC selector filter queries (before semicolon)."""

    def __init__(self, cache: DynamicIfcCompletionCache):
        self.cache = cache

    def get_completions(self, document: Document, complete_event):
        """Generate completions for filter queries."""
        text = document.text
        cursor_pos = document.cursor_position

        # Only provide completions for filter queries (before first semicolon)
        if ";" in text:
            semicolon_pos = text.find(";")
            if cursor_pos > semicolon_pos:
                return  # Cursor is after semicolon - let value completer handle it

        # Get text before cursor for analysis
        text_before_cursor = text[:cursor_pos]

        # Find the current word being typed
        word_match = re.search(r"[^,+\s]*$", text_before_cursor)
        if word_match:
            current_word = word_match.group()
            start_position = -len(current_word) if current_word else 0
        else:
            current_word = ""
            start_position = 0

        # Determine context and provide appropriate completions
        completions = self._get_contextual_completions(text_before_cursor, current_word)

        # Filter and yield completions
        for completion_text in sorted(completions):
            if not current_word or completion_text.lower().startswith(
                current_word.lower()
            ):
                yield Completion(text=completion_text, start_position=start_position)

    def _get_contextual_completions(
        self, text_before_cursor: str, current_word: str
    ) -> Set[str]:
        """Get contextual completions based on the current position in the filter query."""
        completions = set()

        # Analyze context
        context = self._analyze_filter_context(text_before_cursor)

        if context["expecting_class"]:
            # User is likely typing an IFC class name
            completions.update(self.cache.ifc_classes_in_model)

        if context["expecting_attribute_or_keyword"]:
            # User typed "IfcWall, " - offer attributes and filter keywords
            relevant_classes = self.cache.extract_ifc_classes_from_query(
                text_before_cursor
            )

            # Add attributes for relevant classes
            class_attributes = self.cache.get_attributes_for_classes(relevant_classes)
            completions.update(class_attributes)

            # Add filter keywords
            completions.update(self.cache.filter_keywords)

            # Add property set patterns
            completions.add("Pset_")
            completions.add("/Pset_.*Common/")
            completions.add("Qto_")
            completions.add("/Qto_.*/")

        if context["expecting_property_name"]:
            # User typed "Pset_WallCommon." - offer properties from that pset
            pset_name = context["current_pset"]
            if pset_name and pset_name in self.cache.properties_by_pset:
                completions.update(self.cache.properties_by_pset[pset_name])

        if context["expecting_value"]:
            # User typed "Name=" - this is harder to predict, but we can offer some hints
            if context["current_attribute"] == "material":
                # Could suggest known material names, but that requires more analysis
                pass
            elif context["current_attribute"] == "location":
                # Could suggest known spatial element names
                pass

        if context["at_start_or_after_separator"]:
            # Beginning of query or after comma/plus - offer IFC classes
            completions.update(self.cache.ifc_classes_in_model)

        return completions

    def _analyze_filter_context(self, text: str) -> Dict[str, Any]:
        """Analyze the current context in a filter query."""
        context = {
            "expecting_class": False,
            "expecting_attribute_or_keyword": False,
            "expecting_property_name": False,
            "expecting_value": False,
            "at_start_or_after_separator": False,
            "current_pset": None,
            "current_attribute": None,
        }

        # Remove leading/trailing whitespace for analysis
        text = text.strip()

        if not text:
            context["at_start_or_after_separator"] = True
            context["expecting_class"] = True
            return context

        # Check if we're at the start or after a separator
        if text.endswith((",", "+")):
            context["at_start_or_after_separator"] = True
            context["expecting_class"] = True
            return context

        # Look for the last complete "segment" (everything after last comma or plus)
        last_segment_match = re.search(r"[,+]\s*([^,+]*)$", text)
        if last_segment_match:
            last_segment = last_segment_match.group(1).strip()
        else:
            last_segment = text

        # Analyze the last segment
        if not last_segment:
            context["expecting_class"] = True
            context["at_start_or_after_separator"] = True
        elif re.match(r"^Ifc[A-Za-z0-9]*$", last_segment):
            # Currently typing an IFC class
            context["expecting_class"] = True
        elif re.match(r"^Ifc[A-Za-z0-9]+\s*$", last_segment):
            # Just finished an IFC class, expecting comma or attribute
            context["expecting_attribute_or_keyword"] = True
        elif "=" in last_segment:
            # There's an equals sign, might be expecting a value
            parts = last_segment.split("=")
            if len(parts) == 2 and not parts[1].strip():
                context["expecting_value"] = True
                context["current_attribute"] = parts[0].strip()
        elif "." in last_segment and not last_segment.endswith("."):
            # Property set reference like "Pset_WallCommon.FireRating"
            if last_segment.count(".") == 1:
                context["expecting_attribute_or_keyword"] = True
        elif last_segment.endswith("."):
            # User typed "Pset_WallCommon." - expecting property name
            context["expecting_property_name"] = True
            pset_candidate = last_segment[:-1]
            if pset_candidate in self.cache.property_sets:
                context["current_pset"] = pset_candidate
        else:
            # Default case - could be typing attribute or keyword
            context["expecting_attribute_or_keyword"] = True

        return context


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

        # Determine if we're in filter query or value extraction context
        if ";" not in text:
            # No semicolon - definitely filter query
            yield from self.filter_completer.get_completions(document, complete_event)
        else:
            # Has semicolon - check which side of first semicolon cursor is on
            first_semicolon_pos = text.find(";")
            if cursor_pos <= first_semicolon_pos:
                # Cursor is before or at first semicolon - filter query
                yield from self.filter_completer.get_completions(
                    document, complete_event
                )
            else:
                # Cursor is after first semicolon - value extraction
                yield from self.value_completer.get_completions(
                    document, complete_event
                )

    def get_debug_info(self) -> Dict[str, Any]:
        """Get debug information about the completion system."""
        return self.value_completer.get_debug_info()


def create_dynamic_completion_system(model: ifcopenshell.file):
    """Create the enhanced completion system with both filter and value support."""
    cache = DynamicIfcCompletionCache(model)
    completer = CombinedIfcCompleter(cache)
    return cache, completer


# Backwards compatibility aliases
create_enhanced_completion_system = create_dynamic_completion_system
