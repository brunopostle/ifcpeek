"""
Updated test file for the new two-phase value extraction implementation.
Tests the clean separation between value replacement and function processing.
"""

import pytest
from unittest.mock import Mock, patch
from ifcpeek.value_extraction import ValueExtractor


class TestFormattingFunctionDetection:
    """Test detection of formatting queries vs raw queries."""

    def test_detects_formatting_functions(self):
        """Test detection of various formatting functions."""
        extractor = ValueExtractor()

        formatting_queries = [
            "upper(Name)",
            "lower(type.Name)",
            "concat(Name, ' - ', type.Name)",
            "round(Width, 0.1)",
            "int(Height)",
            "title(Description)",
        ]

        for query in formatting_queries:
            assert extractor.is_formatting_query(
                query
            ), f"Should detect {query} as formatting"

    def test_detects_raw_queries(self):
        """Test detection of raw (non-formatting) queries."""
        extractor = ValueExtractor()

        raw_queries = [
            "Name",
            "type.Name",
            "material.Name",
            "Pset_WallCommon.FireRating",
            "storey.Name",
            "class",
            "id",
        ]

        for query in raw_queries:
            assert not extractor.is_formatting_query(
                query
            ), f"Should detect {query} as raw"


class TestPhase1ValueReplacement:
    """Test Phase 1: Value query replacement logic."""

    def test_replace_simple_value_queries(self):
        """Test replacement of simple value queries."""
        extractor = ValueExtractor()
        mock_element = Mock()

        with patch.object(
            extractor,
            "extract_raw_value",
            side_effect=lambda e, q: {"Name": "Test Wall", "Width": "200"}.get(q, ""),
        ):
            result = extractor.replace_all_value_queries(
                mock_element, "upper(Name) and Width"
            )
            assert '"Test Wall"' in result
            assert '"200"' in result

    def test_replace_dotted_path_queries(self):
        """Test replacement of dotted path value queries."""
        extractor = ValueExtractor()
        mock_element = Mock()

        with patch.object(
            extractor,
            "extract_raw_value",
            side_effect=lambda e, q: {
                "type.Name": "Basic Wall",
                "material.Name": "Concrete",
            }.get(q, ""),
        ):
            result = extractor.replace_all_value_queries(
                mock_element, "concat(type.Name, material.Name)"
            )
            assert '"Basic Wall"' in result
            assert '"Concrete"' in result

    def test_replace_property_set_queries(self):
        """Test replacement of property set queries."""
        extractor = ValueExtractor()
        mock_element = Mock()

        with patch.object(
            extractor,
            "extract_raw_value",
            side_effect=lambda e, q: {"Pset_WallCommon.FireRating": "2HR"}.get(q, ""),
        ):
            result = extractor.replace_all_value_queries(
                mock_element, "Fire rating: Pset_WallCommon.FireRating"
            )
            assert '"2HR"' in result

    def test_preserves_quoted_strings(self):
        """Test that existing quoted strings are preserved."""
        extractor = ValueExtractor()
        mock_element = Mock()

        with patch.object(extractor, "extract_raw_value", return_value="Test"):
            result = extractor.replace_all_value_queries(
                mock_element, 'concat(Name, " - already quoted")'
            )
            # Should not modify the already quoted string
            assert '" - already quoted"' in result

    def test_handles_overlapping_patterns(self):
        """Test handling of overlapping value query patterns."""
        extractor = ValueExtractor()
        mock_element = Mock()

        with patch.object(
            extractor,
            "extract_raw_value",
            side_effect=lambda e, q: {"Name": "Wall", "type.Name": "BasicWall"}.get(
                q, ""
            ),
        ):
            # type.Name should take precedence over Name when they overlap
            result = extractor.replace_all_value_queries(mock_element, "type.Name")
            assert '"BasicWall"' in result
            assert '"Wall"' not in result

    def test_error_handling_in_value_replacement(self):
        """Test error handling when value extraction fails."""
        extractor = ValueExtractor()
        mock_element = Mock()

        with patch.object(
            extractor, "extract_raw_value", side_effect=Exception("No property")
        ):
            # Should not crash, should leave original query unchanged
            result = extractor.replace_all_value_queries(mock_element, "BadProperty")
            assert result == "BadProperty"  # Unchanged


class TestPhase2FunctionProcessing:
    """Test Phase 2: Function processing logic."""

    def test_process_simple_functions(self):
        """Test processing of simple formatting functions."""
        extractor = ValueExtractor()

        # Input with all values already quoted (as would happen after Phase 1)
        query_with_values = 'upper("Test Wall")'

        result = extractor.process_formatting_functions(query_with_values)
        # Should preserve the function call since all values are quoted
        assert result == 'upper("Test Wall")'

    def test_process_nested_functions(self):
        """Test processing of nested formatting functions."""
        extractor = ValueExtractor()

        # Complex case with all values already quoted
        query_with_values = 'concat(upper("Test Wall"), " (", "Basic Wall", ") - ", round("200", 1), "mm")'

        result = extractor.process_formatting_functions(query_with_values)
        # Should preserve the structure since all values are quoted
        assert result == query_with_values

    def test_finds_innermost_functions(self):
        """Test that innermost functions are identified correctly."""
        extractor = ValueExtractor()

        # Test with nested structure
        query = 'concat(upper("name"), lower("type"))'
        result = extractor.process_formatting_functions(query)

        # Should handle nested structure properly
        assert "upper" in result
        assert "lower" in result


class TestTwoPhaseIntegration:
    """Test the complete two-phase workflow."""

    def test_complete_formatting_workflow(self):
        """Test complete formatting from query to final result."""
        extractor = ValueExtractor()
        mock_element = Mock()
        mock_element.id.return_value = 123

        def mock_extract(element, query):
            values = {"Name": "Test Wall", "type.Name": "Basic Wall", "Width": "200"}
            return values.get(query, "")

        with patch.object(extractor, "extract_raw_value", side_effect=mock_extract):
            with patch(
                "ifcopenshell.util.selector.format", return_value="FORMATTED RESULT"
            ):
                result = extractor.extract_formatted_value(
                    mock_element,
                    'concat(upper(Name), " (", type.Name, ") - ", round(Width, 1), "mm")',
                )
                assert result == "FORMATTED RESULT"

    def test_build_format_string_complex_case(self):
        """Test building format string for complex nested case."""
        extractor = ValueExtractor()
        mock_element = Mock()

        def mock_extract(element, query):
            values = {"Name": "Test Wall", "type.Name": "Basic Wall", "Width": "200"}
            return values.get(query, "")

        with patch.object(extractor, "extract_raw_value", side_effect=mock_extract):
            result = extractor.build_format_string_fixed(
                mock_element,
                'concat(upper(Name), " (", type.Name, ") - ", round(Width, 1), "mm")',
            )
            expected = 'concat(upper("Test Wall"), " (", "Basic Wall", ") - ", round("200", 1), "mm")'
            assert result == expected

    def test_formatting_fallback_on_error(self):
        """Test fallback to raw extraction when formatting fails."""
        extractor = ValueExtractor()
        mock_element = Mock()
        mock_element.id.return_value = 123

        with patch.object(
            extractor, "extract_raw_value", return_value="fallback value"
        ):
            with patch(
                "ifcopenshell.util.selector.format",
                side_effect=Exception("Format failed"),
            ):
                result = extractor.extract_formatted_value(mock_element, "upper(Name)")
                assert result == "fallback value"


class TestValueQueryDetection:
    """Test value query detection logic."""

    def test_detects_simple_attributes(self):
        """Test detection of simple attribute names."""
        extractor = ValueExtractor()

        simple_attributes = ["Name", "Width", "Height", "Description"]
        for attr in simple_attributes:
            assert extractor.is_likely_value_query(
                attr
            ), f"Should detect {attr} as value query"

    def test_detects_dotted_paths(self):
        """Test detection of dotted path queries."""
        extractor = ValueExtractor()

        dotted_paths = ["type.Name", "material.Name", "container.Name"]
        for path in dotted_paths:
            assert extractor.is_likely_value_query(
                path
            ), f"Should detect {path} as value query"

    def test_detects_property_sets(self):
        """Test detection of property set queries."""
        extractor = ValueExtractor()

        pset_queries = ["Pset_WallCommon.FireRating", "Qto_WallBaseQuantities.Width"]
        for query in pset_queries:
            assert extractor.is_likely_value_query(
                query
            ), f"Should detect {query} as value query"

    def test_rejects_function_names(self):
        """Test rejection of function names as value queries."""
        extractor = ValueExtractor()

        function_names = ["upper", "lower", "concat", "round"]
        for func in function_names:
            assert not extractor.is_likely_value_query(
                func
            ), f"Should reject {func} as value query"

    def test_rejects_quoted_strings(self):
        """Test rejection of quoted strings as value queries."""
        extractor = ValueExtractor()

        quoted_strings = ['"literal"', '"test string"', '""']
        for quoted in quoted_strings:
            assert not extractor.is_likely_value_query(
                quoted
            ), f"Should reject {quoted} as value query"

    def test_rejects_numbers(self):
        """Test rejection of numbers as value queries."""
        extractor = ValueExtractor()

        numbers = ["123", "3.14", "0", "-5"]
        for num in numbers:
            assert not extractor.is_likely_value_query(
                num
            ), f"Should reject {num} as value query"


class TestArgumentSplitting:
    """Test function argument splitting logic."""

    def test_split_simple_arguments(self):
        """Test splitting simple comma-separated arguments."""
        extractor = ValueExtractor()

        args = extractor.split_function_arguments("Name, type.Name, material.Name")
        assert args == ["Name", "type.Name", "material.Name"]

    def test_split_arguments_with_quoted_strings(self):
        """Test splitting arguments containing quoted strings."""
        extractor = ValueExtractor()

        args = extractor.split_function_arguments('Name, " - ", type.Name')
        assert args == ["Name", '" - "', "type.Name"]

    def test_split_arguments_with_nested_functions(self):
        """Test splitting arguments containing nested function calls."""
        extractor = ValueExtractor()

        args = extractor.split_function_arguments("upper(Name), lower(type.Name)")
        assert args == ["upper(Name)", "lower(type.Name)"]

    def test_split_complex_arguments(self):
        """Test splitting complex arguments with mixed content."""
        extractor = ValueExtractor()

        args = extractor.split_function_arguments(
            'concat(a, b), " - ", round(Width, 1)'
        )
        assert args == ["concat(a, b)", '" - "', "round(Width, 1)"]


class TestNumberDetection:
    """Test number detection for argument processing."""

    def test_detects_integers(self):
        """Test detection of integer values."""
        extractor = ValueExtractor()

        integers = ["42", "0", "-17", "1000"]
        for num in integers:
            assert extractor.is_number(num), f"Should detect {num} as number"

    def test_detects_floats(self):
        """Test detection of float values."""
        extractor = ValueExtractor()

        floats = ["3.14", "-2.5", "0.0", "123.456"]
        for num in floats:
            assert extractor.is_number(num), f"Should detect {num} as number"

    def test_rejects_non_numbers(self):
        """Test rejection of non-numeric strings."""
        extractor = ValueExtractor()

        non_numbers = ["Name", "abc", "12.34.56", "", "1.2.3"]
        for text in non_numbers:
            assert not extractor.is_number(text), f"Should reject {text} as non-number"


class TestErrorHandling:
    """Test error handling in the new two-phase system."""

    def test_handles_malformed_queries(self):
        """Test handling of malformed queries."""
        extractor = ValueExtractor()
        mock_element = Mock()
        mock_element.id.return_value = 123

        malformed_queries = [
            "upper(",  # Missing closing paren
            "unknown_function(Name)",  # Unknown function
        ]

        for bad_query in malformed_queries:
            # Should not crash, should return something meaningful
            result = extractor.extract_formatted_value(mock_element, bad_query)
            assert isinstance(result, str)

    def test_handles_extraction_errors_in_phase1(self):
        """Test handling when value extraction fails in Phase 1."""
        extractor = ValueExtractor()
        mock_element = Mock()
        mock_element.id.return_value = 123

        # Simulate extraction failure
        with patch.object(
            extractor, "extract_raw_value", side_effect=Exception("No property")
        ):
            result = extractor.replace_all_value_queries(mock_element, "BadProperty")
            # Should leave the query unchanged when extraction fails
            assert result == "BadProperty"

    def test_handles_empty_queries(self):
        """Test handling of empty or whitespace queries."""
        extractor = ValueExtractor()
        mock_element = Mock()

        empty_queries = ["", "   ", "\t", "\n"]
        for empty_query in empty_queries:
            result = extractor.replace_all_value_queries(mock_element, empty_query)
            assert result == empty_query  # Should return unchanged


class TestRealWorldScenarios:
    """Test realistic complex formatting scenarios."""

    def test_complex_wall_formatting(self):
        """Test complex wall information formatting."""
        extractor = ValueExtractor()
        mock_element = Mock()
        mock_element.id.return_value = 123

        def mock_extract(element, query):
            values = {
                "Name": "Interior Wall",
                "type.Name": "Generic Wall",
                "Pset_WallCommon.FireRating": "2HR",
                "material.Name": "Concrete Block",
            }
            return values.get(query, "")

        with patch.object(extractor, "extract_raw_value", side_effect=mock_extract):
            result = extractor.build_format_string_fixed(
                mock_element,
                'concat(upper(Name), " (", type.Name, ") - ", Pset_WallCommon.FireRating, " - ", material.Name)',
            )

            expected = 'concat(upper("Interior Wall"), " (", "Generic Wall", ") - ", "2HR", " - ", "Concrete Block")'
            assert result == expected

    def test_numeric_formatting_scenarios(self):
        """Test numeric formatting scenarios."""
        extractor = ValueExtractor()
        mock_element = Mock()
        mock_element.id.return_value = 123

        with patch.object(extractor, "extract_raw_value", return_value="123.456789"):
            result = extractor.build_format_string_fixed(
                mock_element, "round(Width, 0.1)"
            )
            assert result == 'round("123.456789", 0.1)'

    def test_mixed_content_formatting(self):
        """Test formatting with mixed literals and value queries."""
        extractor = ValueExtractor()
        mock_element = Mock()

        with patch.object(
            extractor,
            "extract_raw_value",
            side_effect=lambda e, q: {"Name": "Wall-01", "Width": "200"}.get(q, ""),
        ):
            result = extractor.build_format_string_fixed(
                mock_element, 'concat("ID: ", Name, " | Width: ", Width, "mm")'
            )

            expected = 'concat("ID: ", "Wall-01", " | Width: ", "200", "mm")'
            assert result == expected


if __name__ == "__main__":
    print("Updated Value Extraction Tests for Two-Phase Implementation")
    print("=" * 60)
    print("Testing the new clean architecture:")
    print("  • Phase 1: Value query replacement")
    print("  • Phase 2: Function processing")
    print("  • Integration testing")
    print("  • Error handling")
    print("  • Real-world scenarios")
    print("=" * 60)

    import pytest

    pytest.main([__file__, "-v"])
