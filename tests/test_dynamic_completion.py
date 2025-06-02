"""Corrected tests for dynamic_completion.py module."""

import os
from unittest.mock import Mock, patch
from prompt_toolkit.document import Document

# Enable debug mode for testing
os.environ["IFCPEEK_DEBUG"] = "1"


class TestDynamicIfcCompletionCache:
    """Test the completion cache building functionality."""

    def test_cache_creation_with_minimal_model(self):
        """Test cache creation with a minimal mock model."""
        from ifcpeek.dynamic_completion import DynamicIfcCompletionCache

        # Create a minimal mock model
        mock_model = Mock()

        # Mock entities for iteration
        mock_wall = Mock()
        mock_wall.is_a.return_value = "IfcWall"
        mock_door = Mock()
        mock_door.is_a.return_value = "IfcDoor"

        mock_model.__iter__ = Mock(return_value=iter([mock_wall, mock_door]))
        mock_model.by_type.return_value = []  # No property sets

        cache = DynamicIfcCompletionCache(mock_model)

        # Basic assertions
        assert cache.model is mock_model
        assert "IfcWall" in cache.ifc_classes_in_model
        assert "IfcDoor" in cache.ifc_classes_in_model
        assert len(cache.selector_keywords) > 0
        assert "material" in cache.filter_keywords

    def test_cache_handles_empty_model(self):
        """Test cache creation with empty model."""
        from ifcpeek.dynamic_completion import DynamicIfcCompletionCache

        mock_model = Mock()
        mock_model.__iter__ = Mock(return_value=iter([]))
        mock_model.by_type.return_value = []

        cache = DynamicIfcCompletionCache(mock_model)

        assert len(cache.ifc_classes_in_model) == 0
        assert len(cache.property_sets) == 0
        # Should still have basic keywords
        assert len(cache.selector_keywords) > 0

    def test_cache_handles_model_iteration_failure(self, capsys):
        """Test cache handles model that fails during iteration."""
        from ifcpeek.dynamic_completion import DynamicIfcCompletionCache

        mock_model = Mock()
        mock_model.__iter__ = Mock(side_effect=Exception("Iteration failed"))
        mock_model.by_type.return_value = []

        # Should not crash, but should have empty cache
        cache = DynamicIfcCompletionCache(mock_model)

        assert len(cache.ifc_classes_in_model) == 0

        # Should log warning
        captured = capsys.readouterr()
        assert "Could not iterate over model" in captured.err

    def test_cache_property_set_extraction(self):
        """Test property set extraction from model."""
        from ifcpeek.dynamic_completion import DynamicIfcCompletionCache

        mock_model = Mock()
        mock_model.__iter__ = Mock(return_value=iter([]))

        # Mock property set
        mock_pset = Mock()
        mock_pset.Name = "Pset_WallCommon"

        # Mock property within the set
        mock_prop = Mock()
        mock_prop.Name = "FireRating"
        mock_pset.HasProperties = [mock_prop]

        # Make by_type return our mock property set for IfcPropertySet
        def mock_by_type(entity_type):
            if entity_type == "IfcPropertySet":
                return [mock_pset]
            return []

        mock_model.by_type = mock_by_type

        cache = DynamicIfcCompletionCache(mock_model)

        assert "Pset_WallCommon" in cache.property_sets
        assert "Pset_WallCommon" in cache.properties_by_pset
        assert "FireRating" in cache.properties_by_pset["Pset_WallCommon"]

    def test_cache_handles_property_set_failure(self, capsys):
        """Test cache handles property set extraction failure."""
        from ifcpeek.dynamic_completion import DynamicIfcCompletionCache

        mock_model = Mock()
        mock_model.__iter__ = Mock(return_value=iter([]))
        mock_model.by_type = Mock(side_effect=Exception("by_type failed"))

        # Should not crash
        cache = DynamicIfcCompletionCache(mock_model)

        assert len(cache.property_sets) == 0
        # Should still have basic functionality
        assert len(cache.selector_keywords) > 0

        # Should log warnings
        captured = capsys.readouterr()
        assert "Could not scan IfcPropertySet" in captured.err

    def test_extract_ifc_classes_from_query(self):
        """Test extraction of IFC classes from filter query."""
        from ifcpeek.dynamic_completion import DynamicIfcCompletionCache

        mock_model = Mock()
        mock_model.__iter__ = Mock(return_value=iter([]))
        mock_model.by_type.return_value = []

        cache = DynamicIfcCompletionCache(mock_model)
        cache.ifc_classes_in_model = {"IfcWall", "IfcDoor", "IfcWindow"}

        # Test simple query
        classes = cache.extract_ifc_classes_from_query("IfcWall")
        assert "IfcWall" in classes

        # Test complex query
        classes = cache.extract_ifc_classes_from_query(
            "IfcWall, IfcDoor, material=concrete"
        )
        assert "IfcWall" in classes
        assert "IfcDoor" in classes

        # Test query with no IFC classes
        classes = cache.extract_ifc_classes_from_query("material=concrete")
        assert classes == cache.ifc_classes_in_model  # Should return all


class TestFilterQueryCompleter:
    """Test the filter query completer."""

    def create_test_cache(self):
        """Create a test cache with some basic data."""
        from ifcpeek.dynamic_completion import DynamicIfcCompletionCache

        mock_model = Mock()
        mock_model.__iter__ = Mock(return_value=iter([]))
        mock_model.by_type.return_value = []

        cache = DynamicIfcCompletionCache(mock_model)
        cache.ifc_classes_in_model = {"IfcWall", "IfcDoor", "IfcWindow"}
        cache.property_sets = {"Pset_WallCommon", "Pset_DoorCommon"}
        cache.properties_by_pset = {
            "Pset_WallCommon": {"FireRating", "ThermalTransmittance"},
            "Pset_DoorCommon": {"SecurityRating", "SoundReduction"},
        }

        return cache

    def test_completer_creation(self):
        """Test basic completer creation."""
        from ifcpeek.dynamic_completion import FilterQueryCompleter

        cache = self.create_test_cache()
        completer = FilterQueryCompleter(cache)

        assert completer.cache is cache

    def test_ifc_class_completion(self):
        """Test completion of IFC class names."""
        from ifcpeek.dynamic_completion import FilterQueryCompleter

        cache = self.create_test_cache()
        completer = FilterQueryCompleter(cache)

        # Test completion at start of query
        document = Document("IfcW", cursor_position=4)
        completions = list(completer.get_completions(document, None))

        completion_texts = [c.text for c in completions]
        assert "IfcWall" in completion_texts
        assert "IfcWindow" in completion_texts

    def test_no_completion_after_semicolon(self):
        """Test that filter completer doesn't complete after semicolon."""
        from ifcpeek.dynamic_completion import FilterQueryCompleter

        cache = self.create_test_cache()
        completer = FilterQueryCompleter(cache)

        # Cursor after semicolon should not get completions
        document = Document("IfcWall ; ", cursor_position=9)
        completions = list(completer.get_completions(document, None))

        assert len(completions) == 0

    def test_context_analysis_empty_query(self):
        """Test context analysis with empty query."""
        from ifcpeek.dynamic_completion import FilterQueryCompleter

        cache = self.create_test_cache()
        completer = FilterQueryCompleter(cache)

        # Test empty query
        context = completer._analyze_filter_context("")
        assert context["expecting_class"] is True
        assert context["at_start_or_after_separator"] is True

    def test_context_analysis_after_ifc_class_with_comma(self):
        """Test context analysis after IFC class with comma and space."""
        from ifcpeek.dynamic_completion import FilterQueryCompleter

        cache = self.create_test_cache()
        completer = FilterQueryCompleter(cache)

        # Test after IFC class with comma and space
        context = completer._analyze_filter_context("IfcWall, ")
        assert context["expecting_attribute_or_keyword"] is True

    def test_context_analysis_after_comma_separator(self):
        """Test context analysis when text ends with comma separator."""
        from ifcpeek.dynamic_completion import FilterQueryCompleter

        cache = self.create_test_cache()
        completer = FilterQueryCompleter(cache)

        # Test text ending with comma (should expect new class)
        context = completer._analyze_filter_context("IfcWall,")
        assert context["at_start_or_after_separator"] is True
        assert context["expecting_class"] is True


class TestDynamicIfcValueCompleter:
    """Test the value extraction completer."""

    def create_test_system(self):
        """Create a test completion system."""
        from ifcpeek.dynamic_completion import (
            DynamicIfcCompletionCache,
            DynamicIfcValueCompleter,
        )

        mock_model = Mock()
        mock_model.__iter__ = Mock(return_value=iter([]))
        mock_model.by_type.return_value = []

        cache = DynamicIfcCompletionCache(mock_model)
        completer = DynamicIfcValueCompleter(cache)

        return cache, completer

    def test_value_completer_creation(self):
        """Test basic value completer creation."""
        cache, completer = self.create_test_system()

        assert completer.cache is cache
        assert completer.resolver is not None

    def test_no_completion_before_semicolon(self):
        """Test that value completer doesn't complete before semicolon."""
        cache, completer = self.create_test_system()

        # No semicolon should not get completions
        document = Document("IfcWall", cursor_position=6)
        completions = list(completer.get_completions(document, None))

        assert len(completions) == 0

    def test_completion_after_semicolon(self):
        """Test completion works after semicolon."""
        cache, completer = self.create_test_system()

        # Mock the resolver to return some completions
        mock_completions = {"Name", "class", "id"}
        completer.resolver.get_completions_for_path = Mock(
            return_value=mock_completions
        )

        document = Document("IfcWall ; ", cursor_position=9)
        completions = list(completer.get_completions(document, None))

        # Should get some completions
        completion_texts = [c.text for c in completions]
        assert "Name" in completion_texts or "class" in completion_texts

    def test_debug_info(self):
        """Test debug info generation."""
        cache, completer = self.create_test_system()

        debug_info = completer.get_debug_info()

        assert "total_classes" in debug_info
        assert "cached_attributes" in debug_info
        assert "property_sets" in debug_info
        assert isinstance(debug_info["total_classes"], int)


class TestCombinedIfcCompleter:
    """Test the combined completer that routes between filter and value completion."""

    def create_combined_completer(self):
        """Create a combined completer for testing."""
        from ifcpeek.dynamic_completion import (
            DynamicIfcCompletionCache,
            CombinedIfcCompleter,
        )

        mock_model = Mock()
        mock_model.__iter__ = Mock(return_value=iter([]))
        mock_model.by_type.return_value = []

        cache = DynamicIfcCompletionCache(mock_model)
        completer = CombinedIfcCompleter(cache)

        return completer

    def test_combined_completer_creation(self):
        """Test creation of combined completer."""
        completer = self.create_combined_completer()

        assert completer.cache is not None
        assert completer.filter_completer is not None
        assert completer.value_completer is not None

    def test_routing_to_filter_completer(self):
        """Test that queries without semicolon go to filter completer."""
        completer = self.create_combined_completer()

        # Mock the filter completer
        mock_completion = Mock()
        mock_completion.text = "IfcWall"
        completer.filter_completer.get_completions = Mock(
            return_value=[mock_completion]
        )
        completer.value_completer.get_completions = Mock(return_value=[])

        document = Document("IfcW", cursor_position=4)
        completions = list(completer.get_completions(document, None))

        # Should call filter completer
        completer.filter_completer.get_completions.assert_called_once()
        completer.value_completer.get_completions.assert_not_called()

        assert len(completions) > 0

    def test_routing_to_value_completer(self):
        """Test that queries after semicolon go to value completer."""
        completer = self.create_combined_completer()

        # Mock the completers
        mock_completion = Mock()
        mock_completion.text = "Name"
        completer.filter_completer.get_completions = Mock(return_value=[])
        completer.value_completer.get_completions = Mock(return_value=[mock_completion])

        document = Document("IfcWall ; ", cursor_position=9)
        list(completer.get_completions(document, None))

        # Should call value completer
        completer.value_completer.get_completions.assert_called_once()
        # Filter completer should not be called for value extraction
        completer.filter_completer.get_completions.assert_not_called()


class TestDynamicContextResolver:
    """Test the dynamic context resolver for value paths."""

    def create_resolver(self):
        """Create a test resolver."""
        from ifcpeek.dynamic_completion import (
            DynamicIfcCompletionCache,
            DynamicContextResolver,
        )

        mock_model = Mock()
        mock_model.__iter__ = Mock(return_value=iter([]))
        mock_model.by_type.return_value = []

        cache = DynamicIfcCompletionCache(mock_model)
        resolver = DynamicContextResolver(cache)

        return resolver

    def test_resolver_creation(self):
        """Test basic resolver creation."""
        resolver = self.create_resolver()

        assert resolver.cache is not None

    @patch("ifcopenshell.util.selector.filter_elements")
    def test_get_completions_empty_filter_result(self, mock_filter):
        """Test handling of empty filter results."""
        resolver = self.create_resolver()

        # Mock empty filter result
        mock_filter.return_value = []

        completions = resolver.get_completions_for_path("IfcWall", "Name")

        # Should return fallback completions
        assert len(completions) > 0
        assert "Name" in completions or "class" in completions

    @patch("ifcopenshell.util.selector.filter_elements")
    @patch("ifcopenshell.util.selector.get_element_value")
    def test_get_completions_with_results(self, mock_get_value, mock_filter):
        """Test completion generation with actual results."""
        resolver = self.create_resolver()

        # Mock filter results
        mock_element = Mock()
        mock_filter.return_value = [mock_element]

        # Mock value extraction - return a mock object with some attributes
        mock_result = Mock()
        mock_result.Name = "TestWall"
        mock_result.Description = "Test Description"
        mock_get_value.return_value = mock_result

        completions = resolver.get_completions_for_path("IfcWall", "type")

        # Should include selector keywords and discovered attributes
        assert len(completions) > 0

    @patch("ifcopenshell.util.selector.filter_elements")
    def test_resolver_handles_filter_failure(self, mock_filter):
        """Test resolver handles filter element failure."""
        resolver = self.create_resolver()

        # Make filter_elements fail
        mock_filter.side_effect = Exception("Filter failed")

        # Should return fallback completions
        completions = resolver.get_completions_for_path("IfcWall", "Name")

        assert len(completions) > 0

    def test_fallback_completions(self):
        """Test fallback completion generation."""
        resolver = self.create_resolver()

        fallback = resolver._get_fallback_completions()

        assert len(fallback) > 0
        assert "Name" in fallback
        assert "class" in fallback
        assert "id" in fallback


class TestModuleFunctions:
    """Test module-level functions."""

    def test_create_dynamic_completion_system(self):
        """Test the main factory function."""
        from ifcpeek.dynamic_completion import create_dynamic_completion_system

        mock_model = Mock()
        mock_model.__iter__ = Mock(return_value=iter([]))
        mock_model.by_type.return_value = []

        cache, completer = create_dynamic_completion_system(mock_model)

        assert cache is not None
        assert completer is not None
        assert cache.model is mock_model

    def test_backwards_compatibility_alias(self):
        """Test that backwards compatibility alias exists."""
        from ifcpeek.dynamic_completion import create_enhanced_completion_system

        mock_model = Mock()
        mock_model.__iter__ = Mock(return_value=iter([]))
        mock_model.by_type.return_value = []

        # Should work the same as create_dynamic_completion_system
        cache, completer = create_enhanced_completion_system(mock_model)

        assert cache is not None
        assert completer is not None
