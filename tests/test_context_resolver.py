"""
Fixed test_context_resolver.py that properly mocks the enhanced completion system.

The key changes:
1. Mock ifcopenshell.util.element.get_psets() to return realistic property set data
2. Update test expectations to match the enhanced completion behavior
3. Add tests for the new property set completion features
"""

import pytest
from unittest.mock import Mock, patch
from ifcpeek.dynamic_completion import DynamicContextResolver, DynamicIfcCompletionCache


@pytest.fixture
def mock_cache():
    """Create a mock cache for testing."""
    cache = Mock(spec=DynamicIfcCompletionCache)
    cache.selector_keywords = {"Name", "class", "id", "type", "material", "storey"}
    cache.property_sets = {
        "Pset_WallCommon",
        "Pset_DoorCommon",
        "Qto_WallBaseQuantities",
        "Qto_BeamBaseQuantities",
    }
    cache.common_attributes = {"Name", "Description", "GlobalId", "Tag"}
    cache.properties_by_pset = {
        "Pset_WallCommon": {"FireRating", "LoadBearing", "ThermalTransmittance"},
        "Qto_WallBaseQuantities": {"NetArea", "NetVolume", "GrossArea"},
        "Qto_BeamBaseQuantities": {"GrossSurfaceArea", "Length", "NetVolume"},
    }

    # Add the missing model attribute that the resolver expects
    cache.model = Mock()

    return cache


class TestContextResolverInitialization:
    """Test context resolver initialization and basic setup."""

    def test_resolver_initializes_with_cache(self, mock_cache):
        """Test resolver initializes correctly with cache."""
        resolver = DynamicContextResolver(mock_cache)

        assert resolver.cache is mock_cache

    def test_resolver_has_fallback_completions(self, mock_cache):
        """Test resolver can provide fallback completions."""
        resolver = DynamicContextResolver(mock_cache)

        fallback = resolver._get_fallback_completions()

        assert len(fallback) > 0
        assert "Name" in fallback
        assert "class" in fallback
        assert "id" in fallback


class TestBasicPathCompletion:
    """Test basic value path completion logic."""

    def test_completes_simple_attribute_paths(self, mock_cache):
        """Test completion of simple attribute paths."""
        resolver = DynamicContextResolver(mock_cache)

        # Mock filter_elements to return some entities
        mock_element = Mock()
        mock_element.Name = "Test Wall"
        mock_element.Description = "A test wall"
        mock_element.GlobalId = "guid123"

        with patch(
            "ifcopenshell.util.selector.filter_elements", return_value=[mock_element]
        ):
            completions = resolver.get_completions_for_path("IfcWall", "")

            # Should include entity attributes and selector keywords
            assert "Name" in completions
            assert "class" in completions
            assert "id" in completions

    def test_completes_nested_attribute_paths(self, mock_cache):
        """Test completion of nested attribute paths like 'type.Name'."""
        resolver = DynamicContextResolver(mock_cache)

        # Mock entity with type relationship
        mock_wall = Mock()
        mock_wall_type = Mock()
        mock_wall_type.Name = "BasicWall"
        mock_wall_type.Description = "Standard wall type"

        with patch(
            "ifcopenshell.util.selector.filter_elements", return_value=[mock_wall]
        ):
            with patch(
                "ifcopenshell.util.selector.get_element_value",
                return_value=mock_wall_type,
            ):
                completions = resolver.get_completions_for_path("IfcWall", "type")

                # Should include attributes from the type object
                assert len(completions) > 0
                # Should include selector keywords that work on any object
                assert "Name" in completions or any(
                    "Name" in str(c) for c in completions
                )

    def test_handles_empty_filter_results(self, mock_cache):
        """Test handling when filter query returns no results."""
        resolver = DynamicContextResolver(mock_cache)

        with patch("ifcopenshell.util.selector.filter_elements", return_value=[]):
            completions = resolver.get_completions_for_path("IfcNonExistent", "")

            # Should return fallback completions
            assert len(completions) > 0
            assert "Name" in completions
            assert "class" in completions


class TestPropertySetNameCompletion:
    """Test property set name completion - NEW TESTS for enhanced functionality."""

    def test_completes_qto_property_set_names(self, mock_cache):
        """Test completion of Qto_ property set names."""
        resolver = DynamicContextResolver(mock_cache)

        mock_element = Mock()

        # Mock get_psets to return realistic property set data
        mock_psets = {
            "Qto_BeamBaseQuantities": {
                "id": 123,
                "GrossSurfaceArea": 15.5,
                "Length": 3.0,
                "NetVolume": 0.45,
            },
            "Qto_BeamCommon": {"id": 124, "Status": "New"},
        }

        with patch(
            "ifcopenshell.util.selector.filter_elements", return_value=[mock_element]
        ):
            with patch("ifcopenshell.util.element.get_psets", return_value=mock_psets):
                completions = resolver.get_completions_for_path("IfcBeam", "Qto_")

                # Should return matching property set names
                assert "Qto_BeamBaseQuantities" in completions
                assert "Qto_BeamCommon" in completions
                # Should not include non-matching property sets
                assert "Pset_WallCommon" not in completions

    def test_completes_pset_property_set_names(self, mock_cache):
        """Test completion of Pset_ property set names."""
        resolver = DynamicContextResolver(mock_cache)

        mock_element = Mock()

        mock_psets = {
            "Pset_WallCommon": {"id": 125, "FireRating": "2HR", "LoadBearing": True},
            "Pset_WallThermal": {"id": 126, "ThermalTransmittance": 0.25},
        }

        with patch(
            "ifcopenshell.util.selector.filter_elements", return_value=[mock_element]
        ):
            with patch("ifcopenshell.util.element.get_psets", return_value=mock_psets):
                completions = resolver.get_completions_for_path("IfcWall", "Pset_")

                assert "Pset_WallCommon" in completions
                assert "Pset_WallThermal" in completions

    def test_falls_back_to_cache_for_property_set_names(self, mock_cache):
        """Test fallback to cache when dynamic extraction fails."""
        resolver = DynamicContextResolver(mock_cache)

        mock_element = Mock()

        with patch(
            "ifcopenshell.util.selector.filter_elements", return_value=[mock_element]
        ):
            # Mock get_psets to fail
            with patch(
                "ifcopenshell.util.element.get_psets",
                side_effect=Exception("Mock error"),
            ):
                completions = resolver.get_completions_for_path("IfcWall", "Pset_")

                # Should fall back to cached property sets
                assert "Pset_WallCommon" in completions
                assert "Pset_DoorCommon" in completions


class TestPropertySetPropertyCompletion:
    """Test property set property completion - NEW TESTS for enhanced functionality."""

    def test_completes_properties_within_property_set(self, mock_cache):
        """Test completion of properties within a specific property set."""
        resolver = DynamicContextResolver(mock_cache)

        mock_element = Mock()

        mock_psets = {
            "Qto_BeamBaseQuantities": {
                "id": 123,
                "GrossSurfaceArea": 15.5,
                "Length": 3.0,
                "NetVolume": 0.45,
                "OuterSurfaceArea": 12.0,
            }
        }

        with patch(
            "ifcopenshell.util.selector.filter_elements", return_value=[mock_element]
        ):
            with patch("ifcopenshell.util.element.get_psets", return_value=mock_psets):
                completions = resolver.get_completions_for_path(
                    "IfcBeam", "Qto_BeamBaseQuantities."
                )

                # Should return actual properties from the property set
                assert "GrossSurfaceArea" in completions
                assert "Length" in completions
                assert "NetVolume" in completions
                assert "OuterSurfaceArea" in completions
                # Should not include the 'id' key
                assert "id" not in completions

    def test_falls_back_to_cache_for_property_set_properties(self, mock_cache):
        """Test fallback to cache for property set properties."""
        resolver = DynamicContextResolver(mock_cache)

        mock_element = Mock()

        with patch(
            "ifcopenshell.util.selector.filter_elements", return_value=[mock_element]
        ):
            # Mock get_psets to return empty result
            with patch("ifcopenshell.util.element.get_psets", return_value={}):
                completions = resolver.get_completions_for_path(
                    "IfcBeam", "Qto_BeamBaseQuantities."
                )

                # Should fall back to cached properties
                assert "GrossSurfaceArea" in completions
                assert "Length" in completions
                assert "NetVolume" in completions


class TestEntityInspection:
    """Test entity inspection and attribute extraction."""

    def test_inspects_entity_attributes_via_dict(self, mock_cache):
        """Test inspection of entity attributes via __dict__."""
        resolver = DynamicContextResolver(mock_cache)

        # Create a simple object with __dict__ instead of using Mock
        class SimpleEntity:
            def __init__(self):
                self.Name = "Test Wall"
                self.Description = "A wall"
                self.Tag = "W01"
                self.ObjectType = "Wall"
                self.private_attr = "should_be_ignored"  # lowercase, should be filtered

        entity = SimpleEntity()
        attributes = resolver._get_entity_attributes(entity)

        # Should include uppercase attributes
        assert "Name" in attributes
        assert "Description" in attributes
        assert "Tag" in attributes
        assert "ObjectType" in attributes
        # Should exclude lowercase/private attributes
        assert "private_attr" not in attributes

    def test_handles_entity_inspection_failure(self, mock_cache):
        """Test handling when entity inspection fails."""
        resolver = DynamicContextResolver(mock_cache)

        class BrokenEntity:
            @property
            def __dict__(self):
                raise RuntimeError("Inspection failed")

        mock_entity = BrokenEntity()

        # Should not crash and return empty set
        attributes = resolver._get_entity_attributes(mock_entity)
        assert isinstance(attributes, set)


class TestResultInspection:
    """Test inspection of value extraction results."""

    def test_inspects_list_results(self, mock_cache):
        """Test inspection of list/tuple results."""
        resolver = DynamicContextResolver(mock_cache)

        # Test list result
        list_result = ["item1", "item2", "item3"]
        attributes = resolver._inspect_result(list_result)

        assert "count" in attributes
        assert "0" in attributes
        assert "1" in attributes
        assert "2" in attributes
        # Should include selector keywords
        assert len(attributes.intersection(mock_cache.selector_keywords)) > 0

    def test_inspects_object_results(self, mock_cache):
        """Test inspection of object results."""
        resolver = DynamicContextResolver(mock_cache)

        # Use a simple class instead of Mock to avoid recursion issues
        class SimpleResult:
            def __init__(self):
                self.Name = "Test Object"
                self.Value = 42
                self.Hidden = "data"

        result = SimpleResult()
        attributes = resolver._inspect_result(result)

        # Should include object attributes
        assert "Name" in attributes
        assert "Value" in attributes
        # Should include selector keywords
        assert len(attributes.intersection(mock_cache.selector_keywords)) > 0

    def test_handles_none_result(self, mock_cache):
        """Test handling of None results."""
        resolver = DynamicContextResolver(mock_cache)

        attributes = resolver._inspect_result(None)

        # Should return empty set for None
        assert attributes == set()

    def test_inspects_large_lists_with_limits(self, mock_cache):
        """Test that large list inspection respects limits."""
        resolver = DynamicContextResolver(mock_cache)

        # Large list
        large_list = list(range(100))
        attributes = resolver._inspect_result(large_list)

        assert "count" in attributes
        # Should include some indices but not all 100
        indices = {attr for attr in attributes if attr.isdigit()}
        assert len(indices) > 0
        assert len(indices) <= 10  # Should be limited


class TestComplexQueryScenarios:
    """Test complex value path resolution scenarios - updated for enhanced behavior."""

    def test_resolves_property_set_paths(self, mock_cache):
        """Test resolution of property set paths - updated for enhanced completion."""
        resolver = DynamicContextResolver(mock_cache)

        mock_element = Mock()

        # Mock get_psets to return realistic property set data
        mock_psets = {
            "Pset_WallCommon": {
                "id": 123,
                "FireRating": "2HR",
                "ThermalTransmittance": 0.25,
                "LoadBearing": True,
            }
        }

        with patch(
            "ifcopenshell.util.selector.filter_elements", return_value=[mock_element]
        ):
            with patch("ifcopenshell.util.element.get_psets", return_value=mock_psets):
                # Test property set name completion
                completions = resolver.get_completions_for_path(
                    "IfcWall", "Pset_WallCommon"
                )

                # With enhanced completion, this should return matching property set names
                # Since "Pset_WallCommon" exactly matches a property set, it should be returned
                assert len(completions) > 0
                assert "Pset_WallCommon" in completions

    def test_resolves_nested_object_paths(self, mock_cache):
        """Test resolution of deeply nested object paths - focus on not crashing."""
        resolver = DynamicContextResolver(mock_cache)

        mock_element = Mock()

        with patch(
            "ifcopenshell.util.selector.filter_elements", return_value=[mock_element]
        ):
            # Mock a nested path that could realistically occur
            mock_location = Mock()
            mock_location.__dict__ = {"x": 10.0, "y": 20.0, "z": 30.0}

            def mock_get_value(element, path):
                if path == "ObjectPlacement.Location":
                    return mock_location
                else:
                    raise Exception(f"Unknown path: {path}")

            with patch(
                "ifcopenshell.util.selector.get_element_value",
                side_effect=mock_get_value,
            ):
                completions = resolver.get_completions_for_path(
                    "IfcWall", "ObjectPlacement.Location"
                )

                # Should not crash and should provide some useful completions
                assert len(completions) > 0

                # Should include selector keywords as minimum useful completion
                assert len(completions.intersection(mock_cache.selector_keywords)) > 0

    def test_handles_material_layer_scenarios(self, mock_cache):
        """Test resolution for material layer scenarios - corrected expectations."""
        resolver = DynamicContextResolver(mock_cache)

        mock_element = Mock()

        # Create a realistic list that represents material layers
        mock_material_list = [
            {"Name": "Layer 0", "Thickness": 100},
            {"Name": "Layer 1", "Thickness": 110},
            {"Name": "Layer 2", "Thickness": 120},
        ]

        with patch(
            "ifcopenshell.util.selector.filter_elements", return_value=[mock_element]
        ):
            with patch(
                "ifcopenshell.util.selector.get_element_value",
                return_value=mock_material_list,
            ):
                completions = resolver.get_completions_for_path(
                    "IfcWall", "material.item"
                )

                # Should handle list results properly
                assert len(completions) > 0

                # Should include list-specific completions
                assert "count" in completions
                assert "0" in completions  # List indices

                # Should include selector keywords
                assert len(completions.intersection(mock_cache.selector_keywords)) > 0


class TestErrorHandlingAndRecovery:
    """Test error handling and recovery in context resolution."""

    def test_handles_filter_element_failure(self, mock_cache):
        """Test handling when filter_elements fails."""
        resolver = DynamicContextResolver(mock_cache)

        with patch(
            "ifcopenshell.util.selector.filter_elements",
            side_effect=Exception("Filter failed"),
        ):
            completions = resolver.get_completions_for_path("BadQuery[", "Name")

            # Should return fallback completions
            assert len(completions) > 0
            assert "Name" in completions
            assert "class" in completions

    def test_handles_value_extraction_failure(self, mock_cache):
        """Test handling when get_element_value fails."""
        resolver = DynamicContextResolver(mock_cache)

        mock_element = Mock()

        with patch(
            "ifcopenshell.util.selector.filter_elements", return_value=[mock_element]
        ):
            with patch(
                "ifcopenshell.util.selector.get_element_value",
                side_effect=Exception("Value extraction failed"),
            ):
                completions = resolver.get_completions_for_path(
                    "IfcWall", "BadProperty"
                )

                # Should return fallback completions
                assert len(completions) > 0
                assert "Name" in completions

    def test_handles_partial_extraction_failures(self, mock_cache):
        """Test handling when some elements succeed and some fail in value extraction."""
        resolver = DynamicContextResolver(mock_cache)

        mock_element1 = Mock()
        mock_element2 = Mock()
        mock_elements = [mock_element1, mock_element2]

        def mock_get_value(element, path):
            if element is mock_element1:
                # Return a simple object that can be inspected
                result = Mock()
                result.__dict__ = {"Name": "Good Result", "Value": 42}
                return result
            else:
                raise Exception("Extraction failed for element 2")

        with patch(
            "ifcopenshell.util.selector.filter_elements", return_value=mock_elements
        ):
            with patch(
                "ifcopenshell.util.selector.get_element_value",
                side_effect=mock_get_value,
            ):
                completions = resolver.get_completions_for_path("IfcWall", "type")

                # Should return completions from successful extractions plus fallbacks
                assert len(completions) > 0
                assert "Name" in completions  # From either extraction or fallback

    def test_handles_malformed_value_paths(self, mock_cache):
        """Test handling of malformed or complex value paths."""
        resolver = DynamicContextResolver(mock_cache)

        mock_element = Mock()

        with patch(
            "ifcopenshell.util.selector.filter_elements", return_value=[mock_element]
        ):
            # Test various malformed paths
            malformed_paths = [
                "type.",  # Trailing dot
                ".Name",  # Leading dot
                "type..Name",  # Double dots
                "type.Name.",  # Trailing dot after valid path
                "",  # Empty path (should work)
                "type.Name.invalid.very.deep.path",  # Very deep path
            ]

            for path in malformed_paths:
                # Should not crash
                completions = resolver.get_completions_for_path("IfcWall", path)
                assert isinstance(completions, set)
                # Should provide at least some fallback completions
                if path == "":  # Empty path should work normally
                    assert len(completions) > 0

    def test_handles_property_set_extraction_failure(self, mock_cache):
        """Test handling when property set extraction fails - NEW TEST."""
        resolver = DynamicContextResolver(mock_cache)

        mock_element = Mock()

        with patch(
            "ifcopenshell.util.selector.filter_elements", return_value=[mock_element]
        ):
            # Mock get_psets to fail
            with patch(
                "ifcopenshell.util.element.get_psets",
                side_effect=Exception("Property set extraction failed"),
            ):
                # Test property set name completion
                completions = resolver.get_completions_for_path("IfcWall", "Pset_")

                # Should fall back to cached property sets
                assert len(completions) > 0
                cached_psets = {
                    name
                    for name in mock_cache.property_sets
                    if name.startswith("Pset_")
                }
                assert len(completions.intersection(cached_psets)) > 0

                # Test property set property completion
                completions = resolver.get_completions_for_path(
                    "IfcWall", "Pset_WallCommon."
                )

                # Should fall back to cached properties
                assert len(completions) > 0
                assert "FireRating" in completions  # From cache
                assert "LoadBearing" in completions
                assert "ThermalTransmittance" in completions
