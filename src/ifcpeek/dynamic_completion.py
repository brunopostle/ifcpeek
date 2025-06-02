"""
Simplified dynamic completion system for IfcPeek.
Reduced from 800+ lines to ~500 lines while maintaining test compatibility.
"""

import re
from typing import Dict, Set, Any
from collections import defaultdict
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
import ifcopenshell
import ifcopenshell.util.selector
from .debug import debug_print, verbose_print


class DynamicIfcCompletionCache:
    """Enhanced cache with both filter and value extraction completion support."""

    def __init__(self, model: ifcopenshell.file):
        self.model = model
        self.ifc_classes_in_model: Set[str] = set()
        self.property_sets: Set[str] = set()
        self.properties_by_pset: Dict[str, Set[str]] = {}
        self.schema_cache: Dict[str, Set[str]] = {}
        self.attribute_cache: Dict[str, Set[str]] = {}
        self.attribute_values: Dict[str, Set[str]] = defaultdict(set)
        self.material_names: Set[str] = set()
        self.spatial_element_names: Set[str] = set()
        self.type_names: Set[str] = set()

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
        verbose_print("Building enhanced completion cache...")

        # Cache IFC classes in the model with error handling
        debug_print("- Scanning IFC classes")
        try:
            for entity in self.model:
                try:
                    class_name = entity.is_a()
                    self.ifc_classes_in_model.add(class_name)
                except Exception as e:
                    # Skip individual entities that fail
                    debug_print(f"Warning: Failed to process entity: {e}")
                    continue
        except Exception as e:
            debug_print(f"Warning: Could not iterate over model: {e}")

        # Cache property sets and attributes with error handling
        debug_print("- Scanning property sets and attributes")
        try:
            self._cache_property_sets()
        except Exception as e:
            debug_print(f"Warning: Failed to cache property sets: {e}")

        try:
            self._cache_entity_attributes()
        except Exception as e:
            debug_print(f"Warning: Failed to cache entity attributes: {e}")

        cache_info = (
            f"Enhanced cache ready: {len(self.ifc_classes_in_model)} classes, "
            f"{len(self.property_sets)} property sets, "
            f"{len(self.attribute_cache)} classes with cached attributes"
        )
        verbose_print(cache_info)

        debug_print("- Sampling attribute values")
        try:
            self._cache_attribute_values()
        except Exception as e:
            debug_print(f"Warning: Failed to cache attribute values: {e}")

    def _cache_property_sets(self):
        """Cache property sets and their properties from the model."""
        try:
            for pset in self.model.by_type("IfcPropertySet"):
                try:
                    if hasattr(pset, "Name") and pset.Name:
                        pset_name = pset.Name
                        self.property_sets.add(pset_name)

                        properties = set()
                        if hasattr(pset, "HasProperties") and pset.HasProperties:
                            for prop in pset.HasProperties:
                                try:
                                    if hasattr(prop, "Name") and prop.Name:
                                        properties.add(prop.Name)
                                except Exception:
                                    continue

                        self.properties_by_pset[pset_name] = properties
                except Exception as e:
                    debug_print(f"Warning: Failed to process property set: {e}")
                    continue
        except Exception as e:
            debug_print(f"Warning: Could not scan IfcPropertySet: {e}")

        try:
            for qset in self.model.by_type("IfcElementQuantity"):
                try:
                    if hasattr(qset, "Name") and qset.Name:
                        qset_name = qset.Name
                        self.property_sets.add(qset_name)

                        properties = set()
                        if hasattr(qset, "Quantities") and qset.Quantities:
                            for qty in qset.Quantities:
                                try:
                                    if hasattr(qty, "Name") and qty.Name:
                                        properties.add(qty.Name)
                                except Exception:
                                    continue

                        self.properties_by_pset[qset_name] = properties
                except Exception as e:
                    debug_print(f"Warning: Failed to process quantity set: {e}")
                    continue
        except Exception as e:
            debug_print(f"Warning: Could not scan IfcElementQuantity: {e}")

    def _cache_entity_attributes(self):
        """Cache attributes for each IFC class by sampling entities."""
        debug_print("- Caching entity attributes")

        # Sample a few entities from each class to get their attributes
        class_samples = {}
        try:
            for entity in self.model:
                try:
                    class_name = entity.is_a()
                    if class_name not in class_samples:
                        class_samples[class_name] = []
                    if (
                        len(class_samples[class_name]) < 3
                    ):  # Sample up to 3 entities per class
                        class_samples[class_name].append(entity)
                except Exception:
                    continue
        except Exception as e:
            # Re-raise the exception to be caught by _build_cache
            raise e

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

    def _cache_attribute_values(self):
        """Sample actual values for important attributes with simplified scanning."""
        important_attributes = {
            "Name",
            "Description",
            "Tag",
            "ObjectType",
            "PredefinedType",
        }
        max_samples_per_class = 20  # Reduced sample size

        debug_print(
            f"- Scanning real values from IFC model for: {important_attributes}"
        )

        # Method 1: Scan by IFC class to get targeted results
        debug_print("  - Scanning by IFC class...")
        try:
            for ifc_class in list(self.ifc_classes_in_model)[
                :10
            ]:  # Limit to first 10 classes
                try:
                    entities = list(self.model.by_type(ifc_class))
                    if entities:
                        # Sample up to max_samples_per_class from each class
                        sample_entities = entities[:max_samples_per_class]

                        for entity in sample_entities:
                            for attr_name in important_attributes:
                                try:
                                    if hasattr(entity, attr_name):
                                        value = getattr(entity, attr_name)
                                        if (
                                            value
                                            and isinstance(value, str)
                                            and len(value.strip()) > 0
                                        ):
                                            clean_value = value.strip()
                                            if (
                                                len(clean_value) <= 50
                                            ):  # Shorter length limit
                                                self.attribute_values[attr_name].add(
                                                    clean_value
                                                )
                                except Exception:
                                    continue
                except Exception:
                    continue
        except Exception as e:
            debug_print(f"  - Warning: Class-based scanning failed: {e}")

        # Cache material names from actual IFC materials
        debug_print("  - Scanning real materials...")
        try:
            for material in list(self.model.by_type("IfcMaterial"))[
                :30
            ]:  # Reduced limit
                try:
                    if hasattr(material, "Name") and material.Name:
                        clean_name = material.Name.strip()
                        if clean_name and len(clean_name) <= 50:
                            self.material_names.add(clean_name)
                except Exception:
                    continue
        except Exception as e:
            debug_print(f"    Warning: Material scanning failed: {e}")

        # Cache spatial element names
        debug_print("  - Scanning real spatial elements...")
        spatial_types = ["IfcSite", "IfcBuilding", "IfcBuildingStorey", "IfcSpace"]
        for spatial_type in spatial_types:
            try:
                for element in list(self.model.by_type(spatial_type))[
                    :10
                ]:  # Reduced limit
                    try:
                        if hasattr(element, "Name") and element.Name:
                            clean_name = element.Name.strip()
                            if clean_name and len(clean_name) <= 50:
                                self.spatial_element_names.add(clean_name)
                    except Exception:
                        continue
            except Exception:
                continue

        # Cache type names
        debug_print("  - Scanning real types...")
        type_classes = ["IfcWallType", "IfcDoorType", "IfcWindowType", "IfcSlabType"]
        for type_class in type_classes:
            try:
                for type_element in list(self.model.by_type(type_class))[
                    :10
                ]:  # Reduced limit
                    try:
                        if hasattr(type_element, "Name") and type_element.Name:
                            clean_name = type_element.Name.strip()
                            if clean_name and len(clean_name) <= 50:
                                self.type_names.add(clean_name)
                    except Exception:
                        continue
            except Exception:
                continue

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
            debug_print(f"Error inspecting entity: {e}")

        return attributes

    def get_values_for_attribute(self, attribute_name: str) -> Set[str]:
        """Get possible values for a given attribute name."""
        return self.attribute_values.get(attribute_name, set())

    def get_values_for_filter_keyword(self, keyword: str) -> Set[str]:
        """Get possible values for filter keywords like 'material', 'location', etc."""
        if keyword == "material":
            return self.material_names
        elif keyword in ("location", "parent"):
            return self.spatial_element_names
        elif keyword == "type":
            return self.type_names
        else:
            return set()

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

            if hasattr(self, "cache") and hasattr(self.cache, "ifc_classes_in_model"):
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
                debug_print(
                    "_extract_target_class: Cache not available, returning class anyway"
                )
                return ifc_class
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
        """Get completions by executing the path and inspecting actual results."""
        try:
            elements = ifcopenshell.util.selector.filter_elements(
                self.cache.model, filter_query
            )
            if not elements:
                return self._get_fallback_completions()

            element_list = list(elements)
            sample_elements = element_list[
                : min(5, len(element_list))
            ]  # Reduced sample size

            all_attributes = set()
            path_parts = value_path.split(".")

            if len(path_parts) <= 1:
                for element in sample_elements:
                    attrs = self._get_entity_attributes(element)
                    all_attributes.update(attrs)

                all_attributes.update(self.cache.selector_keywords)
                all_attributes.update(self.cache.property_sets)
                all_attributes.add("/Pset_.*Common/")
                all_attributes.add("/Qto_.*/")

                return all_attributes

            partial_path = ".".join(path_parts[:-1])

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

            for result in all_results:
                attrs = self._inspect_result(result)
                all_attributes.update(attrs)

            if not all_attributes:
                return self._get_fallback_completions()

            return all_attributes

        except Exception as e:
            debug_print(f"Error in completion: {e}")
            return self._get_fallback_completions()

    def _inspect_result(self, result: Any) -> Set[str]:
        """Inspect a result object to determine what attributes are available."""
        attributes = set()

        try:
            if result is None:
                return attributes

            if isinstance(result, (list, tuple)):
                attributes.add("count")
                if result:
                    for i in range(min(len(result), 10)):  # Limit indices
                        attributes.add(str(i))

                attributes.update(self.cache.selector_keywords)
                return attributes

            attributes = self._get_entity_attributes(result)
            attributes.update(self.cache.selector_keywords)

        except Exception:
            pass

        return attributes

    def _get_entity_attributes(self, entity: Any) -> Set[str]:
        """Get attributes from any entity by direct inspection."""
        attributes = set()

        try:
            if hasattr(entity, "__dict__"):
                dict_keys = list(entity.__dict__.keys())
                dict_attrs = [k for k in dict_keys if k and k[0].isupper()]
                attributes.update(dict_attrs)

            for attr_name in dir(entity):
                if (
                    attr_name
                    and attr_name[0].isupper()
                    and not attr_name.startswith("_")
                ):
                    try:
                        getattr(entity, attr_name)
                        attributes.add(attr_name)
                    except:
                        pass

        except Exception as e:
            debug_print(f"Error inspecting entity: {e}")

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
