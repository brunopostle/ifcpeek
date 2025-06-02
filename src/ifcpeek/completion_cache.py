"""
IFC completion cache module - extracted from dynamic_completion.py
Handles model scanning and cache building for tab completion.
"""

from typing import Dict, Set, Any
from collections import defaultdict
from .debug import debug_print, verbose_print


class DynamicIfcCompletionCache:
    """Cache for IFC model data to support tab completion."""

    def __init__(self, model):
        self.model = model
        self.ifc_classes_in_model: Set[str] = set()
        self.property_sets: Set[str] = set()
        self.properties_by_pset: Dict[str, Set[str]] = {}
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

        # Filter syntax keywords
        self.filter_keywords: Set[str] = {
            "material",
            "type",
            "location",
            "parent",
            "classification",
            "query",
        }

        # Common IFC attributes
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
        """Build comprehensive cache from IFC model."""
        verbose_print("Building completion cache...")

        try:
            self._cache_ifc_classes()
            self._cache_property_sets()
            self._cache_entity_attributes()
            self._cache_sample_values()
        except Exception as e:
            debug_print(f"Cache building failed: {e}")

        verbose_print(
            f"Cache ready: {len(self.ifc_classes_in_model)} classes, "
            f"{len(self.property_sets)} property sets"
        )

    def _cache_ifc_classes(self):
        """Cache IFC classes present in the model."""
        debug_print("Caching IFC classes...")
        try:
            for entity in self.model:
                try:
                    class_name = entity.is_a()
                    self.ifc_classes_in_model.add(class_name)
                except Exception:
                    continue
        except Exception as e:
            debug_print(f"Could not iterate over model: {e}")

    def _cache_property_sets(self):
        """Cache property sets and their properties."""
        debug_print("Caching property sets...")

        # Cache IfcPropertySet
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
                except Exception:
                    continue
        except Exception as e:
            debug_print(f"Could not scan IfcPropertySet: {e}")

        # Cache IfcElementQuantity
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
                except Exception:
                    continue
        except Exception as e:
            debug_print(f"Could not scan IfcElementQuantity: {e}")

    def _cache_entity_attributes(self):
        """Cache attributes for each IFC class by sampling entities."""
        debug_print("Caching entity attributes...")

        # Sample entities from each class
        class_samples = {}
        try:
            for entity in self.model:
                try:
                    class_name = entity.is_a()
                    if class_name not in class_samples:
                        class_samples[class_name] = []
                    if len(class_samples[class_name]) < 3:
                        class_samples[class_name].append(entity)
                except Exception:
                    continue
        except Exception as e:
            debug_print(f"Could not sample entities: {e}")
            return

        # Extract attributes from samples
        for class_name, entities in class_samples.items():
            attributes = set()
            attributes.update(self.common_attributes)

            for entity in entities:
                entity_attrs = self._get_entity_attributes(entity)
                attributes.update(entity_attrs)

            self.attribute_cache[class_name] = attributes

    def _cache_sample_values(self):
        """Cache sample values for important attributes."""
        debug_print("Caching sample attribute values...")

        important_attributes = {
            "Name",
            "Description",
            "Tag",
            "ObjectType",
            "PredefinedType",
        }
        max_samples = 50

        # Scan by IFC class
        try:
            for ifc_class in list(self.ifc_classes_in_model)[:10]:  # Limit classes
                try:
                    entities = list(self.model.by_type(ifc_class))[:max_samples]

                    for entity in entities:
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
                                        if len(clean_value) <= 100:
                                            self.attribute_values[attr_name].add(
                                                clean_value
                                            )
                            except Exception:
                                continue
                except Exception:
                    continue
        except Exception as e:
            debug_print(f"Value caching failed: {e}")

        # Cache materials, spatial elements, types
        self._cache_special_entities()

    def _cache_special_entities(self):
        """Cache special entity types for filter completion."""
        # Materials
        try:
            for material in list(self.model.by_type("IfcMaterial"))[:50]:
                try:
                    if hasattr(material, "Name") and material.Name:
                        clean_name = material.Name.strip()
                        if clean_name and len(clean_name) <= 50:
                            self.material_names.add(clean_name)
                except Exception:
                    continue
        except Exception:
            pass

        # Spatial elements
        spatial_types = ["IfcSite", "IfcBuilding", "IfcBuildingStorey", "IfcSpace"]
        for spatial_type in spatial_types:
            try:
                for element in list(self.model.by_type(spatial_type))[:20]:
                    try:
                        if hasattr(element, "Name") and element.Name:
                            clean_name = element.Name.strip()
                            if clean_name and len(clean_name) <= 50:
                                self.spatial_element_names.add(clean_name)
                    except Exception:
                        continue
            except Exception:
                continue

        # Types
        type_classes = ["IfcWallType", "IfcDoorType", "IfcWindowType", "IfcSlabType"]
        for type_class in type_classes:
            try:
                for type_element in list(self.model.by_type(type_class))[:20]:
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
        """Get attributes from entity by inspection."""
        attributes = set()

        try:
            # Get attributes from __dict__
            if hasattr(entity, "__dict__"):
                dict_attrs = [k for k in entity.__dict__.keys() if k and k[0].isupper()]
                attributes.update(dict_attrs)

            # Get attributes from dir()
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
        except Exception:
            pass

        return attributes

    def get_values_for_attribute(self, attribute_name: str) -> Set[str]:
        """Get possible values for attribute."""
        return self.attribute_values.get(attribute_name, set())

    def get_values_for_filter_keyword(self, keyword: str) -> Set[str]:
        """Get possible values for filter keywords."""
        if keyword == "material":
            return self.material_names
        elif keyword in ("location", "parent"):
            return self.spatial_element_names
        elif keyword == "type":
            return self.type_names
        return set()

    def extract_ifc_classes_from_query(self, filter_query: str) -> Set[str]:
        """Extract IFC class names from filter query."""
        if not filter_query.strip():
            return self.ifc_classes_in_model

        import re

        classes = set()
        query_parts = re.split(r"[,+]", filter_query)

        for part in query_parts:
            part = part.strip()
            ifc_classes = re.findall(r"\bIfc[A-Za-z0-9]*\b", part)
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
                all_attributes.update(self.common_attributes)

        return all_attributes
