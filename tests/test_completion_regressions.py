"""
Regression tests for completion system fixes.

These tests ensure that specific completion bugs that were fixed stay fixed.
"""

import pytest
from unittest.mock import Mock, patch
from prompt_toolkit.document import Document
from ifcpeek.completion import IfcCompleter


def create_mock_model_with_walls():
    """Create a mock IFC model with walls and properties."""
    mock_model = Mock()

    # Mock schema
    mock_schema = Mock()
    hierarchy = [
        ("IfcRoot", None),
        ("IfcObjectDefinition", "IfcRoot"),
        ("IfcObject", "IfcObjectDefinition"),
        ("IfcProduct", "IfcObject"),
        ("IfcElement", "IfcProduct"),
        ("IfcBuildingElement", "IfcElement"),
        ("IfcWall", "IfcBuildingElement"),
    ]

    class_declarations = {}
    for class_name, parent_name in hierarchy:
        decl = Mock()
        decl.name.return_value = class_name

        # FIXED: supertype needs to be a method that returns the parent, not a property
        if parent_name:
            # Store parent name for later, will resolve after all are created
            decl._parent_name = parent_name
        else:
            decl.supertype = Mock(return_value=None)

        # Add mock attributes
        if class_name == "IfcWall":
            mock_attrs = []
            for attr_name in ["Name", "Description", "GlobalId", "Tag", "ObjectType"]:
                attr = Mock()
                attr.name.return_value = attr_name
                mock_attrs.append(attr)
            decl.all_attributes.return_value = mock_attrs

        class_declarations[class_name] = decl

    # Now resolve parent references to actual objects
    for class_name, decl in class_declarations.items():
        if hasattr(decl, '_parent_name'):
            parent_name = decl._parent_name
            parent_decl = class_declarations.get(parent_name)
            # supertype is a method that returns the parent declaration
            decl.supertype = Mock(return_value=parent_decl)
            delattr(decl, '_parent_name')

    mock_schema.declaration_by_name = lambda name: class_declarations.get(name)

    # FIXED: model.schema is a string (like "IFC4"), not the schema object
    # The code uses ifcopenshell.ifcopenshell_wrapper.schema_by_name() to get the actual schema
    # We need to mock that instead
    mock_model.schema = "IFC4"  # Schema name as string
    mock_model._mock_schema_object = mock_schema  # Store for mocking

    # Mock entities
    entities = []
    for i, name in enumerate(["exterior", "interior", "openwall"]):
        entity = Mock()
        entity.is_a.return_value = "IfcWall"
        entity.Name = name
        entity.GlobalId = f"wall_{i}"

        # Mock relationship attributes as empty tuples
        entity.ConnectedTo = ()
        entity.ConnectedFrom = ()
        entity.HasOpenings = ()
        entity.HasCoverings = ()

        entities.append(entity)

    mock_model.__iter__ = Mock(return_value=iter(entities))

    # Mock by_type
    def mock_by_type(entity_type):
        if entity_type == "IfcWall":
            return entities
        elif entity_type == "IfcPropertySet":
            pset = Mock()
            pset.Name = "Pset_WallCommon"
            prop1 = Mock()
            prop1.Name = "LoadBearing"
            prop2 = Mock()
            prop2.Name = "IsExternal"
            pset.HasProperties = [prop1, prop2]
            return [pset]
        elif entity_type == "IfcElementQuantity":
            return []
        return []

    mock_model.by_type = mock_by_type

    return mock_model, entities


def mock_get_psets(element):
    """Mock get_psets function."""
    if hasattr(element, "is_a") and element.is_a() == "IfcWall":
        return {
            "Pset_WallCommon": {
                "id": 123,
                "LoadBearing": True,
                "IsExternal": False,
                "ThermalTransmittance": 0.25,
            }
        }
    return {}


def mock_filter_elements(model, query):
    """Mock filter_elements function."""
    import re

    ifc_classes = re.findall(r"\bIfcWall\b", query)
    if ifc_classes:
        return model.by_type("IfcWall")
    return []


def mock_get_element_value(element, path):
    """Mock get_element_value function."""
    if not hasattr(element, "is_a"):
        return None

    if path == "Name" and hasattr(element, "Name"):
        return element.Name

    if path == "GlobalId" and hasattr(element, "GlobalId"):
        return element.GlobalId

    # Mock relationship attributes as empty tuples
    if path in ["ConnectedTo", "ConnectedFrom", "HasOpenings", "HasCoverings"]:
        return ()

    return None


@pytest.fixture
def completer():
    """Create a completer with mocked dependencies."""
    mock_model, entities = create_mock_model_with_walls()

    # Mock schema_by_name to return our mock schema object
    def mock_schema_by_name(schema_name):
        return mock_model._mock_schema_object

    with patch("ifcopenshell.util.element.get_psets", side_effect=mock_get_psets):
        with patch(
            "ifcopenshell.util.selector.filter_elements",
            side_effect=mock_filter_elements,
        ):
            with patch(
                "ifcopenshell.util.selector.get_element_value",
                side_effect=mock_get_element_value,
            ):
                with patch(
                    "ifcopenshell.ifcopenshell_wrapper.schema_by_name",
                    side_effect=mock_schema_by_name,
                ):
                    yield IfcCompleter(mock_model)


class TestCompletionRegressions:
    """Test suite for completion regression fixes."""

    def test_space_after_ifc_class_offers_attributes(self, completer):
        """Regression: 'IfcWall ' should offer attributes, not just IFC classes."""
        doc = Document("IfcWall ", cursor_position=8)
        completions = list(completer.get_completions(doc, None))
        completion_texts = {c.text for c in completions}

        # Should offer attributes
        assert "Name" in completion_texts
        assert "Description" in completion_texts

        # Should offer property sets
        assert "Pset_WallCommon" in completion_texts

        # Should also offer IFC classes for union queries
        assert "IfcWall" in completion_texts

        # Should be more than just IFC classes
        assert len(completions) > 20

    def test_property_completion_in_filter_context(self, completer):
        """Regression: 'IfcWall, Pset_WallCommon.' should offer properties."""
        doc = Document("IfcWall, Pset_WallCommon.", cursor_position=25)
        completions = list(completer.get_completions(doc, None))
        completion_texts = {c.text for c in completions}

        # Should offer properties from Pset_WallCommon
        assert "LoadBearing" in completion_texts
        assert "IsExternal" in completion_texts
        assert "ThermalTransmittance" in completion_texts

        # Should have exactly the properties (no IFC classes, etc.)
        assert len(completions) == 3

    def test_attribute_value_completion_in_filter_context(self, completer):
        """Regression: 'IfcWall, Name=' should offer actual Name values."""
        doc = Document("IfcWall, Name=", cursor_position=14)
        completions = list(completer.get_completions(doc, None))
        completion_texts = {c.text for c in completions}

        # Should offer actual Name values from the model
        assert '"exterior"' in completion_texts
        assert '"interior"' in completion_texts
        assert '"openwall"' in completion_texts

        # Should have the values
        assert len(completions) == 3

    def test_property_completion_in_value_context(self, completer):
        """Regression: 'IfcWall; Pset_WallCommon.' should offer properties."""
        doc = Document("IfcWall; Pset_WallCommon.", cursor_position=25)
        completions = list(completer.get_completions(doc, None))
        completion_texts = {c.text for c in completions}

        # Should offer properties from Pset_WallCommon
        assert "LoadBearing" in completion_texts
        assert "IsExternal" in completion_texts
        assert "ThermalTransmittance" in completion_texts

        # Should have exactly the properties
        assert len(completions) == 3

    def test_comma_after_ifc_class_offers_attributes(self, completer):
        """Regression: 'IfcWall, ' should offer attributes and properties."""
        doc = Document("IfcWall, ", cursor_position=9)
        completions = list(completer.get_completions(doc, None))
        completion_texts = {c.text for c in completions}

        # Should offer attributes
        assert "Name" in completion_texts
        assert "Description" in completion_texts

        # Should offer property sets
        assert "Pset_WallCommon" in completion_texts

        # Should offer IFC classes
        assert "IfcWall" in completion_texts

    def test_property_set_prefix_completion(self, completer):
        """Regression: 'IfcWall, P' should offer Pset_* property sets."""
        doc = Document("IfcWall, P", cursor_position=10)
        completions = list(completer.get_completions(doc, None))
        completion_texts = {c.text for c in completions}

        # Should offer property sets starting with P
        assert "Pset_WallCommon" in completion_texts

    def test_value_context_basic_completions(self, completer):
        """Regression: 'IfcWall; ' should offer value extraction paths."""
        doc = Document("IfcWall; ", cursor_position=9)
        completions = list(completer.get_completions(doc, None))
        completion_texts = {c.text for c in completions}

        # Should offer common attributes
        assert "Name" in completion_texts
        assert "Description" in completion_texts

        # Should offer property sets
        assert "Pset_WallCommon" in completion_texts

        # Should offer selector keywords
        assert "type" in completion_texts
        assert "material" in completion_texts

    def test_value_context_property_set_completion(self, completer):
        """Regression: 'IfcWall; P' should offer property sets."""
        doc = Document("IfcWall; P", cursor_position=10)
        completions = list(completer.get_completions(doc, None))
        completion_texts = {c.text for c in completions}

        # Should offer property sets starting with P
        assert "Pset_WallCommon" in completion_texts

    def test_empty_query_offers_ifc_classes(self, completer):
        """Regression: '' should offer IFC classes at start."""
        doc = Document("", cursor_position=0)
        completions = list(completer.get_completions(doc, None))
        completion_texts = {c.text for c in completions}

        # Should offer IFC classes
        assert "IfcWall" in completion_texts

        # Should not offer attributes at the start
        assert "Name" not in completion_texts

    def test_ifc_prefix_filters_classes(self, completer):
        """Regression: 'IfcW' should filter to matching IFC classes."""
        doc = Document("IfcW", cursor_position=4)
        completions = list(completer.get_completions(doc, None))
        completion_texts = {c.text for c in completions}

        # Should offer matching IFC classes
        assert "IfcWall" in completion_texts

        # All completions should start with IfcW
        for text in completion_texts:
            assert text.startswith("IfcW")

    def test_relationship_attributes_in_value_context(self, completer):
        """Regression: 'IfcWall; ' should include relationship attributes like ConnectedTo."""
        doc = Document("IfcWall; ", cursor_position=9)
        completions = list(completer.get_completions(doc, None))
        completion_texts = {c.text for c in completions}

        # Should offer relationship attributes
        assert "ConnectedTo" in completion_texts
        assert "ConnectedFrom" in completion_texts
        assert "HasOpenings" in completion_texts

    def test_relationship_value_completion_returns_empty(self, completer):
        """Regression: 'IfcWall, ConnectedTo=' should not offer completions (relationships are tuples)."""
        doc = Document("IfcWall, ConnectedTo=", cursor_position=21)
        completions = list(completer.get_completions(doc, None))

        # Relationship attributes return tuples, not simple values, so no completions expected
        assert len(completions) == 0

    def test_tuple_attribute_dot_completion(self, completer):
        """Regression: 'IfcWall; ConnectedTo.' should offer tuple access (count) not keywords (building, class)."""
        # Note: This test uses a mock that returns empty tuples
        # In real scenarios with non-empty tuples, numeric indices would also appear
        doc = Document("IfcWall; ConnectedTo.", cursor_position=21)
        completions = list(completer.get_completions(doc, None))
        completion_texts = {c.text for c in completions}

        # Should offer tuple/list access method
        assert "count" in completion_texts

        # Should NOT offer selector keywords that don't apply to tuples
        assert "building" not in completion_texts
        assert "class" not in completion_texts
        assert "type" not in completion_texts

        # Empty tuples won't have numeric indices, but that's expected
        # If the tuple had elements, we'd see "0", "1", etc.

    def test_parent_classes_included(self, completer):
        """Regression: Parent/abstract classes like IfcBuildingElement should be offered."""
        # Test that abstract/parent classes from schema hierarchy are included

        # Get all IFC classes to verify hierarchy traversal worked
        all_classes = completer._get_ifc_classes()

        # Should include parent classes from the hierarchy
        # The mock hierarchy: IfcWall -> IfcBuildingElement -> IfcElement -> IfcProduct -> IfcObject -> IfcObjectDefinition -> IfcRoot
        assert "IfcWall" in all_classes  # Concrete class
        assert "IfcBuildingElement" in all_classes  # Parent class
        assert "IfcElement" in all_classes  # Grandparent class
        assert "IfcProduct" in all_classes  # Great-grandparent class
        assert "IfcObject" in all_classes  # Ancestor
        assert "IfcRoot" in all_classes  # Root class

        # Test completion with prefix
        doc = Document("IfcB", cursor_position=4)
        completions = list(completer.get_completions(doc, None))
        completion_texts = {c.text for c in completions}

        # Should offer parent class
        assert "IfcBuildingElement" in completion_texts
