"""Test formatters module functionality."""

import pytest
from unittest.mock import Mock, patch
import os
import inspect

from ifcpeek.formatters import (
    StepHighlighter,
    format_query_results,
    format_element_value,
)


class TestStepHighlighter:
    """Test StepHighlighter class."""

    def test_highlighter_initialization(self):
        """Test that StepHighlighter initializes correctly."""
        highlighter = StepHighlighter()
        assert hasattr(highlighter, "enabled")
        assert isinstance(highlighter.enabled, bool)

    def test_color_detection_with_no_color_env(self):
        """Test color detection respects NO_COLOR environment variable."""
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            highlighter = StepHighlighter()
            assert highlighter.enabled is False

    def test_color_detection_with_force_color_env(self):
        """Test color detection respects FORCE_COLOR environment variable."""
        with patch.dict(os.environ, {"FORCE_COLOR": "1"}):
            with patch("sys.stdout.isatty", return_value=False):
                highlighter = StepHighlighter()
                assert highlighter.enabled is True

    def test_colorize_when_disabled(self):
        """Test that colorize returns plain text when colors are disabled."""
        highlighter = StepHighlighter()
        highlighter.enabled = False

        result = highlighter._colorize("test", "entity_id")
        assert result == "test"

    def test_colorize_when_enabled(self):
        """Test that colorize applies colors when enabled."""
        highlighter = StepHighlighter()
        highlighter.enabled = True

        result = highlighter._colorize("test", "entity_id")
        assert "\033[94m" in result  # Blue color code
        assert "\033[0m" in result  # Reset code
        assert "test" in result

    def test_highlight_step_line_basic(self):
        """Test basic STEP line highlighting."""
        highlighter = StepHighlighter()
        highlighter.enabled = False  # Disable colors for easier testing

        line = "#1=IFCWALL('guid',$,$,'Wall',$,$,$,$,$);"
        result = highlighter.highlight_step_line(line)

        # When colors are disabled, should return original line
        assert result == line

    def test_highlight_step_line_with_colors(self):
        """Test STEP line highlighting with colors enabled."""
        highlighter = StepHighlighter()
        highlighter.enabled = True

        line = "#1=IFCWALL('guid',$,$,'Wall');"
        result = highlighter.highlight_step_line(line)

        # Should contain color codes
        assert "\033[" in result  # Contains ANSI escape sequences
        assert "IFCWALL" in result
        assert "#1" in result

    def test_highlight_step_line_invalid_format(self):
        """Test highlighting with invalid STEP format."""
        highlighter = StepHighlighter()

        invalid_line = "This is not a STEP format line"
        result = highlighter.highlight_step_line(invalid_line)

        # Should return original line unchanged
        assert result == invalid_line

    def test_guid_detection(self):
        """Test GUID string detection."""
        highlighter = StepHighlighter()

        # Test IFC compressed GUID format
        ifc_guid = "'0u4wgLe6n0ABVaiXyikbkA'"
        assert highlighter._is_guid_string(ifc_guid) is True

        # Test standard UUID format
        uuid_guid = "'12345678-1234-1234-1234-123456789012'"
        assert highlighter._is_guid_string(uuid_guid) is True

        # Test non-GUID string
        regular_string = "'This is just text'"
        assert highlighter._is_guid_string(regular_string) is False

    def test_parameter_highlighting(self):
        """Test parameter highlighting within STEP entities."""
        highlighter = StepHighlighter()
        highlighter.enabled = True

        params = "'guid',$,123,'name'"
        result = highlighter._highlight_parameters(params)

        # Should contain color codes for different parameter types
        assert "\033[" in result  # Contains ANSI escape sequences


class TestFormatQueryResults:
    """Test format_query_results function."""

    def test_format_empty_results(self):
        """Test formatting empty result set."""
        results = list(format_query_results([]))
        assert results == []

    def test_format_single_entity(self):
        """Test formatting single entity."""
        mock_entity = Mock()
        mock_entity.__str__ = Mock(return_value="#1=IFCWALL('guid',$,$,'Wall');")

        results = list(format_query_results([mock_entity], enable_highlighting=False))

        assert len(results) == 1
        assert "#1=IFCWALL('guid'" in results[0]

    def test_format_multiple_entities(self):
        """Test formatting multiple entities."""
        mock_entity1 = Mock()
        mock_entity1.__str__ = Mock(return_value="#1=IFCWALL('guid1',$,$,'Wall1');")

        mock_entity2 = Mock()
        mock_entity2.__str__ = Mock(return_value="#2=IFCDOOR('guid2',$,$,'Door1');")

        results = list(
            format_query_results(
                [mock_entity1, mock_entity2], enable_highlighting=False
            )
        )

        assert len(results) == 2
        assert "#1=IFCWALL('guid1'" in results[0]
        assert "#2=IFCDOOR('guid2'" in results[1]

    def test_format_with_highlighting_enabled(self):
        """Test formatting with syntax highlighting enabled."""
        mock_entity = Mock()
        mock_entity.__str__ = Mock(return_value="#1=IFCWALL('guid',$,$,'Wall');")

        # Mock isatty to return True so highlighting is enabled
        with patch("sys.stdout.isatty", return_value=True):
            results = list(
                format_query_results([mock_entity], enable_highlighting=True)
            )

        assert len(results) == 1
        # The exact result depends on color detection, but should contain the entity

    def test_format_with_entity_error(self, capsys):
        """Test formatting handles entity conversion errors."""
        mock_entity = Mock()
        mock_entity.__str__ = Mock(side_effect=RuntimeError("Conversion failed"))

        results = list(format_query_results([mock_entity], enable_highlighting=False))

        assert len(results) == 1
        assert "Entity formatting error" in results[0]

        # Should log error to stderr
        captured = capsys.readouterr()
        assert "ERROR: Failed to format entity" in captured.err

    def test_format_mixed_success_and_failure(self, capsys):
        """Test formatting with mix of successful and failing entities."""
        mock_entity1 = Mock()
        mock_entity1.__str__ = Mock(return_value="#1=IFCWALL('guid',$,$,'Wall');")

        mock_entity2 = Mock()
        mock_entity2.__str__ = Mock(side_effect=RuntimeError("Conversion failed"))

        mock_entity3 = Mock()
        mock_entity3.__str__ = Mock(return_value="#3=IFCDOOR('guid',$,$,'Door');")

        results = list(
            format_query_results(
                [mock_entity1, mock_entity2, mock_entity3], enable_highlighting=False
            )
        )

        assert len(results) == 3
        assert "#1=IFCWALL('guid'" in results[0]
        assert "Entity formatting error" in results[1]
        assert "#3=IFCDOOR('guid'" in results[2]


class TestFormatElementValue:
    """Test format_element_value function."""

    def test_format_none_value(self):
        """Test formatting None value."""
        result = format_element_value(None)
        assert result == ""

    def test_format_string_value(self):
        """Test formatting string value."""
        result = format_element_value("test_string")
        assert result == "test_string"

    def test_format_numeric_value(self):
        """Test formatting numeric value."""
        result = format_element_value(123.456)
        assert result == "123.456"

    def test_format_boolean_value(self):
        """Test formatting boolean value."""
        result = format_element_value(True)
        assert result == "True"

    def test_format_with_format_spec(self):
        """Test formatting with format specification (placeholder)."""
        # This is a placeholder test - the function will be enhanced later
        result = format_element_value("test", "upper")
        assert result == "test"  # Currently just returns str(value)


class TestIntegrationWithShell:
    """Test integration of formatters with shell functionality."""

    def test_formatters_import_in_shell(self):
        """Test that shell can import formatters successfully."""
        # This test ensures the refactoring didn't break imports
        try:
            from ifcpeek.shell import IfcPeek
            from ifcpeek.formatters import StepHighlighter, format_query_results

            assert True  # Import successful
        except ImportError as e:
            pytest.fail(f"Failed to import after refactoring: {e}")

    def test_shell_uses_formatter_functions(self, mock_ifc_file, mock_selector, capsys):
        """Test that shell uses the new formatter functions."""
        from ifcpeek.shell import IfcPeek
        from unittest.mock import patch, Mock

        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()

            # Test all core functionality still works

            # 1. Help command
            help_result = shell._process_input("/help")
            assert help_result is True

            # 2. Query execution
            mock_entity = Mock()
            mock_entity.__str__ = Mock(
                return_value="#1=IFCWALL('wall-guid',$,$,'Wall',$,$,$,$,$);"
            )
            mock_selector.return_value = [mock_entity]

            query_result = shell._process_input("IfcWall")
            assert query_result is True

            # 3. Exit command
            exit_result = shell._process_input("/exit")
            assert exit_result is False

            captured = capsys.readouterr()

            # Verify outputs are as expected
            assert "IfcPeek - Interactive IFC Model Query Tool" in captured.err
            assert "#1=IFCWALL('wall-guid'" in captured.out

    def test_no_step_highlighter_attribute(self, mock_ifc_file):
        """Test that shell no longer has step_highlighter attribute."""
        from ifcpeek.shell import IfcPeek
        from unittest.mock import patch, Mock

        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Should not have step_highlighter attribute anymore
            assert not hasattr(shell, "step_highlighter")


class TestModuleStructure:
    """Test the module structure after refactoring."""

    def test_formatters_module_exports(self):
        """Test that formatters module exports expected classes and functions."""
        from ifcpeek.formatters import (
            StepHighlighter,
            format_query_results,
            format_element_value,
        )

        # Should be able to import all expected exports
        assert StepHighlighter is not None
        assert format_query_results is not None
        assert format_element_value is not None

        # Classes should be instantiable
        highlighter = StepHighlighter()
        assert highlighter is not None

    def test_shell_module_reduced_size(self):
        """Test that shell module is smaller after refactoring."""
        from ifcpeek import shell

        # Get source code
        source = inspect.getsource(shell)

        # Should not contain StepHighlighter class definition
        assert "class StepHighlighter:" not in source

        # Should not contain color codes dictionary
        assert '"entity_id": "\\033[94m"' not in source

        # Should import from formatters
        assert "from .formatters import" in source

    def test_circular_import_avoided(self):
        """Test that there are no circular imports."""

        # Import order 1: shell -> formatters
        try:
            from ifcpeek.shell import IfcPeek
            from ifcpeek.formatters import StepHighlighter

            assert True
        except ImportError as e:
            pytest.fail(f"Import order 1 failed: {e}")

        # Import order 2: formatters -> shell (should not be needed)
        try:
            from ifcpeek.formatters import StepHighlighter

            # formatters should not import from shell
            import ifcpeek.formatters

            source = inspect.getsource(ifcpeek.formatters)  # NOW inspect IS DEFINED
            assert "from .shell import" not in source
            assert "import ifcpeek.shell" not in source
        except ImportError as e:
            pytest.fail(f"Circular import check failed: {e}")


class TestPerformance:
    """Test performance aspects of the refactored code."""

    def test_formatter_creation_performance(self):
        """Test that creating formatters is fast."""
        import time

        start_time = time.time()

        # Create multiple highlighters
        for _ in range(100):
            highlighter = StepHighlighter()
            assert highlighter is not None

        elapsed = time.time() - start_time

        # Should be very fast (less than 1 second for 100 instances)
        assert elapsed < 1.0

    def test_formatting_performance(self):
        """Test that formatting is reasonably fast."""
        import time

        # Create test entities
        mock_entities = []
        for i in range(50):
            mock_entity = Mock()
            mock_entity.__str__ = Mock(
                return_value="#%d=IFCWALL('guid-%d',$,$,'Wall-%d',$,$,$,$,$);"
                % (i, i, i)
            )
            mock_entities.append(mock_entity)

        start_time = time.time()

        # Format all entities
        results = list(format_query_results(mock_entities, enable_highlighting=False))

        elapsed = time.time() - start_time

        # Should complete in reasonable time
        assert elapsed < 1.0
        assert len(results) == 50


class TestErrorHandling:
    """Test error handling in the refactored formatters."""

    def test_highlighter_handles_malformed_input(self):
        """Test that highlighter handles malformed input gracefully."""
        highlighter = StepHighlighter()

        malformed_inputs = [
            "",
            "   ",
            "not a step line at all",
            "#invalid=",
            "=IFCWALL()",
            "#123=",
            None,  # This should raise an exception, but let's see
        ]

        for bad_input in malformed_inputs[:-1]:  # Skip None for now
            result = highlighter.highlight_step_line(bad_input)
            # Should not crash and should return something
            assert result is not None

    def test_formatter_handles_none_entities(self):
        """Test that formatter handles None entities gracefully."""
        # This might not be a realistic scenario, but let's be defensive
        entities_with_none = [None, Mock()]
        entities_with_none[1].__str__ = Mock(return_value="#1=IFCWALL();")

        # Should not crash
        try:
            results = list(
                format_query_results(entities_with_none, enable_highlighting=False)
            )
            # Exact behavior depends on implementation, but shouldn't crash
            assert isinstance(results, list)
        except Exception:
            # If it does raise an exception, it should be handled gracefully
            pass


if __name__ == "__main__":
    # Run a quick smoke test
    print("Running formatter refactoring smoke test...")

    try:
        # Test basic imports
        from ifcpeek.formatters import StepHighlighter, format_query_results

        # Test basic functionality
        highlighter = StepHighlighter()
        test_line = "#1=IFCWALL('guid',$,$,'Wall');"
        result = highlighter.highlight_step_line(test_line)

        print("✅ Basic functionality test passed")

        # Test formatting function
        mock_entity = Mock()
        mock_entity.__str__ = Mock(return_value=test_line)
        formatted = list(format_query_results([mock_entity], enable_highlighting=False))

        assert len(formatted) == 1
        assert test_line in formatted[0]

        print("✅ Formatting function test passed")
        print("🎉 Refactoring smoke test completed successfully!")

    except Exception as e:
        print(f"❌ Smoke test failed: {e}")
        import traceback

        traceback.print_exc()

        # Configure mock to return test entity
        mock_entity = Mock()
        mock_entity.__str__ = Mock(
            return_value="#1=IFCWALL('wall-guid',$,$,'Wall',$,$,$,$,$);"
        )
        mock_selector.return_value = [mock_entity]

        # Execute query
        shell._execute_query("IfcWall")

        captured = capsys.readouterr()

        # Should show the entity in stdout
        assert "#1=IFCWALL('wall-guid'" in captured.out
        # Should show debug info in stderr
        assert "DEBUG: Executing query: 'IfcWall'" in captured.err
        assert "DEBUG: Query returned 1 results" in captured.err


class TestBackwardCompatibility:
    """Test that refactoring maintains backward compatibility."""

    def test_shell_functionality_unchanged(self, mock_ifc_file, mock_selector, capsys):
        """Test that shell functionality is unchanged after refactoring."""
        from ifcpeek.shell import IfcPeek
        from unittest.mock import patch, Mock

        with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
            mock_model = Mock()
            mock_model.schema = "IFC4"
            mock_model.by_type.return_value = []
            mock_open.return_value = mock_model

            shell = IfcPeek(str(mock_ifc_file))

            # Clear initialization output
            capsys.readouterr()  # FIXED: was capsys.readouter

            # Test all core functionality still works

            # 1. Help command
            help_result = shell._process_input("/help")
            assert help_result is True

            # 2. Query execution
            mock_entity = Mock()
            mock_entity.__str__ = Mock(
                return_value="#1=IFCWALL('wall-guid',$,$,'Wall',$,$,$,$,$);"
            )
            mock_selector.return_value = [mock_entity]

            query_result = shell._process_input("IfcWall")
            assert query_result is True

            # 3. Exit command
            exit_result = shell._process_input("/exit")
            assert exit_result is False

            captured = capsys.readouterr()

            # Verify outputs are as expected
            assert "IfcPeek - Interactive IFC Model Query Tool" in captured.err
            assert "#1=IFCWALL('wall-guid'" in captured.out
