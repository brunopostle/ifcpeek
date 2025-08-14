# comprehensive_bug_test.py
"""
Comprehensive test to validate all the bug fixes with proper mocking.
"""

import os
from unittest.mock import Mock, patch
from prompt_toolkit.document import Document

# Enable debug mode
os.environ["IFCPEEK_DEBUG"] = "1"

def create_realistic_mock():
    """Create a realistic mock that simulates actual IfcOpenShell behavior."""
    mock_model = Mock()
    
    # Mock schema hierarchy
    mock_schema = Mock()
    
    # Create class hierarchy: IfcWall -> IfcBuildingElement -> IfcElement -> IfcProduct -> IfcObject -> IfcObjectDefinition -> IfcRoot
    hierarchy = [
        ("IfcRoot", None),
        ("IfcObjectDefinition", "IfcRoot"),
        ("IfcObject", "IfcObjectDefinition"),
        ("IfcProduct", "IfcObject"),
        ("IfcElement", "IfcProduct"),
        ("IfcBuildingElement", "IfcElement"),
        ("IfcWall", "IfcBuildingElement"),
        ("IfcWindow", "IfcElement"),
        ("IfcDoor", "IfcBuildingElement")
    ]
    
    class_declarations = {}
    for class_name, parent_name in hierarchy:
        decl = Mock()
        decl.name.return_value = class_name
        if parent_name:
            decl.supertype = class_declarations[parent_name]
        else:
            decl.supertype = None
        class_declarations[class_name] = decl
    
    def mock_declaration_by_name(name):
        return class_declarations.get(name)
    
    mock_schema.declaration_by_name = mock_declaration_by_name
    mock_model.schema = mock_schema
    
    # Mock entities
    entities = []
    for class_name in ["IfcWall", "IfcWindow", "IfcDoor"]:
        entity = Mock()
        entity.is_a.return_value = class_name
        entity.Name = f"Test {class_name[3:]}"
        entities.append(entity)
    
    mock_model.__iter__ = Mock(return_value=iter(entities))
    
    # Mock by_type
    def mock_by_type(entity_type):
        result = [e for e in entities if e.is_a() == entity_type]
        
        # Add property sets
        if entity_type == "IfcPropertySet":
            pset = Mock()
            pset.Name = "Pset_WallCommon"
            prop1 = Mock()
            prop1.Name = "LoadBearing"
            prop2 = Mock()
            prop2.Name = "IsExternal"
            prop3 = Mock()
            prop3.Name = "FireRating"
            pset.HasProperties = [prop1, prop2, prop3]
            result = [pset]
        elif entity_type == "IfcElementQuantity":
            qset = Mock()
            qset.Name = "Qto_WallBaseQuantities"
            qty1 = Mock()
            qty1.Name = "NetArea"
            qty2 = Mock()
            qty2.Name = "NetVolume"
            qset.Quantities = [qty1, qty2]
            result = [qset]
        
        print(f"MOCK by_type({entity_type}) returning {len(result)} items")
        return result
    
    mock_model.by_type = mock_by_type
    
    return mock_model

def mock_get_psets(element):
    """Mock get_psets function."""
    if hasattr(element, 'is_a'):
        class_name = element.is_a()
        print(f"MOCK get_psets for {class_name}")
        
        if class_name == "IfcWall":
            return {
                "Pset_WallCommon": {
                    "id": 123,
                    "LoadBearing": True,
                    "IsExternal": False,
                    "FireRating": "2HR",
                    "ThermalTransmittance": 0.25
                },
                "Qto_WallBaseQuantities": {
                    "id": 124,
                    "NetArea": 25.5,
                    "NetVolume": 2.1
                }
            }
        elif class_name == "IfcWindow":
            return {
                "Pset_WindowCommon": {
                    "id": 125,
                    "IsExternal": True,
                    "FireRating": "1HR"
                }
            }
    return {}

def mock_filter_elements(model, query):
    """Mock filter_elements function."""
    print(f"MOCK filter_elements called with: '{query}'")
    
    # Extract IFC classes from query
    import re
    ifc_classes = re.findall(r'\bIfc[A-Za-z0-9]+\b', query)
    print(f"MOCK extracted IFC classes: {ifc_classes}")
    
    results = []
    for ifc_class in ifc_classes:
        class_results = model.by_type(ifc_class)
        results.extend(class_results)
        print(f"MOCK added {len(class_results)} {ifc_class} elements")
    
    print(f"MOCK filter_elements returning {len(results)} total elements")
    return results

def test_all_bugs():
    """Test all bugs comprehensively."""
    print("=" * 70)
    print("COMPREHENSIVE BUG FIX VALIDATION")
    print("=" * 70)
    
    try:
        from ifcpeek.completion import IfcCompleter
        print("✓ Successfully imported IfcCompleter")
    except ImportError as e:
        print(f"❌ Failed to import IfcCompleter: {e}")
        return
    
    mock_model = create_realistic_mock()
    
    with patch('ifcopenshell.util.element.get_psets', side_effect=mock_get_psets):
        with patch('ifcopenshell.util.selector.filter_elements', side_effect=mock_filter_elements):
            
            completer = IfcCompleter(mock_model)
            
            # Test Bug 1: Property sets after multiple IFC classes
            print("\n" + "-" * 50)
            print("BUG 1: Property sets after multiple IFC classes")
            print("-" * 50)
            
            text = "IfcWall, IfcWindow, "
            print(f"Testing: '{text}<TAB>'")
            
            doc = Document(text, cursor_position=len(text))
            completions = list(completer.get_completions(doc, None))
            completion_texts = [c.text for c in completions]
            
            print(f"Found {len(completions)} completions")
            
            has_pset = any("Pset_" in t for t in completion_texts)
            has_qto = any("Qto_" in t for t in completion_texts)
            has_ifc = any("Ifc" in t for t in completion_texts)
            
            print(f"Has Pset_ completions: {has_pset}")
            print(f"Has Qto_ completions: {has_qto}")
            print(f"Has IFC completions: {has_ifc}")
            
            if has_pset or has_qto:
                print("✅ BUG 1 FIXED: Property sets offered after multiple IFC classes")
            else:
                print("❌ BUG 1 NOT FIXED")
                print("Completions found:", sorted(completion_texts)[:10])
            
            # Test Bug 2: Parent classes
            print("\n" + "-" * 50)
            print("BUG 2: Parent class inclusion")
            print("-" * 50)
            
            text = "IfcE"
            print(f"Testing: '{text}<TAB>'")
            
            doc = Document(text, cursor_position=len(text))
            completions = list(completer.get_completions(doc, None))
            completion_texts = [c.text for c in completions]
            
            print(f"Found {len(completions)} completions")
            
            has_element = "IfcElement" in completion_texts
            has_root = "IfcRoot" in completion_texts
            
            print(f"Has IfcElement: {has_element}")
            print(f"Has IfcRoot: {has_root}")
            
            if has_element and has_root:
                print("✅ BUG 2 FIXED: Parent classes included")
            else:
                print("❌ BUG 2 NOT FIXED")
                print("Completions found:", sorted(completion_texts))
            
            # Test Bug 3: Boolean property values
            print("\n" + "-" * 50)
            print("BUG 3: Boolean property value completion")
            print("-" * 50)
            
            text = "IfcWall, Pset_WallCommon.LoadBearing="
            print(f"Testing: '{text}<TAB>'")
            
            doc = Document(text, cursor_position=len(text))
            completions = list(completer.get_completions(doc, None))
            completion_texts = [c.text for c in completions]
            
            print(f"Found {len(completions)} completions")
            
            has_true = "TRUE" in completion_texts
            has_false = "FALSE" in completion_texts
            
            print(f"Has TRUE: {has_true}")
            print(f"Has FALSE: {has_false}")
            
            if has_true and has_false:
                print("✅ BUG 3 FIXED: Boolean values offered")
            else:
                print("❌ BUG 3 NOT FIXED")
                print("Completions found:", sorted(completion_texts))
            
            # Test Bug 4: Property set completion in value context
            print("\n" + "-" * 50)
            print("BUG 4: Property set completion in value context")
            print("-" * 50)
            
            text = "IfcWall, Pset_WallCommon.IsExternal=TRUE; P"
            print(f"Testing: '{text}<TAB>'")
            
            doc = Document(text, cursor_position=len(text))
            completions = list(completer.get_completions(doc, None))
            completion_texts = [c.text for c in completions]
            
            print(f"Found {len(completions)} completions")
            
            has_pset_wall = "Pset_WallCommon" in completion_texts
            has_pset_window = "Pset_WindowCommon" in completion_texts
            
            print(f"Has Pset_WallCommon: {has_pset_wall}")
            print(f"Has Pset_WindowCommon: {has_pset_window}")
            
            if has_pset_wall:
                print("✅ BUG 4 FIXED: Property sets expand in value context")
            else:
                print("❌ BUG 4 NOT FIXED")
                print("Completions found:", sorted(completion_texts))
            
            # Test Bug 5: Property completion within property sets
            print("\n" + "-" * 50)
            print("BUG 5: Property completion within property sets in value context")
            print("-" * 50)
            
            text = "IfcWall, Pset_WallCommon.IsExternal=TRUE; Pset_WallCommon."
            print(f"Testing: '{text}<TAB>'")
            
            doc = Document(text, cursor_position=len(text))
            completions = list(completer.get_completions(doc, None))
            completion_texts = [c.text for c in completions]
            
            print(f"Found {len(completions)} completions")
            
            has_load_bearing = "LoadBearing" in completion_texts
            has_external = "IsExternal" in completion_texts
            has_fire_rating = "FireRating" in completion_texts
            
            print(f"Has LoadBearing: {has_load_bearing}")
            print(f"Has IsExternal: {has_external}")
            print(f"Has FireRating: {has_fire_rating}")
            
            if has_load_bearing and has_external and has_fire_rating:
                print("✅ BUG 5 FIXED: Properties expand within property sets")
            else:
                print("❌ BUG 5 NOT FIXED")
                print("Completions found:", sorted(completion_texts))
    
    print("\n" + "=" * 70)
    print("COMPREHENSIVE TESTING COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    test_all_bugs()
