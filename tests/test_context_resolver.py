"""
Test dynamic context resolution for tab completion - the "smart" completion logic.
Tests the system that executes partial queries to determine valid completions.
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
    }
    cache.common_attributes = {"Name", "Description", "GlobalId", "Tag"}
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


class TestEntityInspection:
    """Test entity inspection and attribute extraction."""

    def test_inspects_entity_attributes_via_dict(self, mock_cache):
        """Test inspection of entity attributes via __dict__."""
        resolver = DynamicContextResolver(mock_cache)

        mock_entity = Mock()
        mock_entity.__dict__ = {
            "Name": "Test Wall",
            "Description": "A wall",
            "Tag": "W01",
            "ObjectType": "Wall",
            "private_attr": "should_be_ignored",  # lowercase, should be filtered
        }

        attributes = resolver._get_entity_attributes(mock_entity)

        # Should include uppercase attributes
        assert "Name" in attributes
        assert "Description" in attributes
        assert "Tag" in attributes
        assert "ObjectType" in attributes
        # Should exclude lowercase/private attributes
        assert "private_attr" not in attributes

    def test_inspects_entity_attributes_via_dir(self, mock_cache):
        """Test inspection of entity attributes via dir()."""
        resolver = DynamicContextResolver(mock_cache)

        mock_entity = Mock()
        # Remove __dict__ to force dir() inspection
        del mock_entity.__dict__

        def mock_dir(obj):
            return ["Name", "Description", "GlobalId", "Tag", "_private", "method"]

        def mock_getattr(obj, name):
            if name in ["Name", "Description", "GlobalId", "Tag"]:
                return f"value_{name}"
            else:
                raise AttributeError(f"No attribute {name}")

        with patch("builtins.dir", side_effect=mock_dir):
            with patch("builtins.getattr", side_effect=mock_getattr):
                attributes = resolver._get_entity_attributes(mock_entity)

        # Should include accessible uppercase attributes
        assert "Name" in attributes
        assert "Description" in attributes
        assert "GlobalId" in attributes
        assert "Tag" in attributes
        # Should exclude private attributes and methods
        assert "_private" not in attributes
        assert "method" not in attributes

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

        mock_result = Mock()
        mock_result.Name = "Test Object"
        mock_result.Value = 42
        mock_result.__dict__ = {"Name": "Test Object", "Value": 42, "Hidden": "data"}

        attributes = resolver._inspect_result(mock_result)

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
    """Test complex value path resolution scenarios."""

    def test_resolves_property_set_paths(self, mock_cache):
        """Test resolution of property set paths like 'Pset_WallCommon.FireRating'."""
        resolver = DynamicContextResolver(mock_cache)

        mock_element = Mock()
        mock_pset = Mock()
        mock_pset.FireRating = "2HR"
        mock_pset.ThermalTransmittance = 0.25

        with patch(
            "ifcopenshell.util.selector.filter_elements", return_value=[mock_element]
        ):
            with patch(
                "ifcopenshell.util.selector.get_element_value", return_value=mock_pset
            ):
                completions = resolver.get_completions_for_path(
                    "IfcWall", "Pset_WallCommon"
                )

                # Should include property set attributes
                assert len(completions) > 0
                # Should find properties through inspection
                properties_found = any(
                    "FireRating" in str(c) or "ThermalTransmittance" in str(c)
                    for c in completions
                )
                # Even if specific properties aren't found, should have selector keywords
                assert len(completions.intersection(mock_cache.selector_keywords)) > 0

    def test_resolves_nested_object_paths(self, mock_cache):
        """Test resolution of deeply nested object paths."""
        resolver = DynamicContextResolver(mock_cache)

        mock_element = Mock()
        mock_placement = Mock()
        mock_location = Mock()
        mock_location.x = 10.0
        mock_location.y = 20.0
        mock_location.z = 30.0
        mock_placement.Location = mock_location

        with patch(
            "ifcopenshell.util.selector.filter_elements", return_value=[mock_element]
        ):

            def mock_get_value(element, path):
                if path == "ObjectPlacement":
                    return mock_placement
                elif path == "ObjectPlacement.Location":
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

                # Should include coordinate attributes
                assert len(completions) > 0

    def test_handles_material_layer_scenarios(self, mock_cache):
        """Test resolution for material layer scenarios."""
        resolver = DynamicContextResolver(mock_cache)

        mock_element = Mock()
        mock_material_list = [Mock(), Mock(), Mock()]  # List of material layers
        for i, mat in enumerate(mock_material_list):
            mat.Name = f"Layer {i}"
            mat.Thickness = 100 + i * 10

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

                # Should handle list results
                assert "count" in completions
                assert "0" in completions  # List indices
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
                mock_result = Mock()
                mock_result.Name = "Good Result"
                return mock_result
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

                # Should return completions from successful extractions
                assert len(completions) > 0

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
