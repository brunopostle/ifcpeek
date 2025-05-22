"""Test custom exception hierarchy."""
import pytest

from ifcpeek.exceptions import (
    IfcPeekError,
    FileNotFoundError,
    InvalidIfcFileError,
    QueryExecutionError,
    ConfigurationError,
)


class TestExceptionHierarchy:
    """Test exception class inheritance and behavior."""

    def test_base_exception_inheritance(self):
        """Test that IfcPeekError inherits from Exception."""
        assert issubclass(IfcPeekError, Exception)

        # Test instantiation
        error = IfcPeekError("Test error")
        assert isinstance(error, Exception)
        assert str(error) == "Test error"

    def test_file_not_found_error_inheritance(self):
        """Test FileNotFoundError inheritance."""
        assert issubclass(FileNotFoundError, IfcPeekError)
        assert issubclass(FileNotFoundError, Exception)

        error = FileNotFoundError("File not found")
        assert isinstance(error, IfcPeekError)
        assert isinstance(error, Exception)
        assert str(error) == "File not found"

    def test_invalid_ifc_file_error_inheritance(self):
        """Test InvalidIfcFileError inheritance."""
        assert issubclass(InvalidIfcFileError, IfcPeekError)
        assert issubclass(InvalidIfcFileError, Exception)

        error = InvalidIfcFileError("Invalid IFC file")
        assert isinstance(error, IfcPeekError)
        assert isinstance(error, Exception)
        assert str(error) == "Invalid IFC file"

    def test_query_execution_error_inheritance(self):
        """Test QueryExecutionError inheritance."""
        assert issubclass(QueryExecutionError, IfcPeekError)
        assert issubclass(QueryExecutionError, Exception)

        error = QueryExecutionError("Query failed")
        assert isinstance(error, IfcPeekError)
        assert isinstance(error, Exception)
        assert str(error) == "Query failed"

    def test_configuration_error_inheritance(self):
        """Test ConfigurationError inheritance."""
        assert issubclass(ConfigurationError, IfcPeekError)
        assert issubclass(ConfigurationError, Exception)

        error = ConfigurationError("Config error")
        assert isinstance(error, IfcPeekError)
        assert isinstance(error, Exception)
        assert str(error) == "Config error"


class TestExceptionHandling:
    """Test exception handling behavior."""

    def test_catch_specific_exceptions(self):
        """Test catching specific exception types."""

        def raise_file_not_found():
            raise FileNotFoundError("Test file not found")

        def raise_invalid_ifc():
            raise InvalidIfcFileError("Test invalid IFC")

        # Test catching specific exceptions
        with pytest.raises(FileNotFoundError):
            raise_file_not_found()

        with pytest.raises(InvalidIfcFileError):
            raise_invalid_ifc()

    def test_catch_base_exception(self):
        """Test catching base IfcPeekError catches all custom exceptions."""
        exceptions_to_test = [
            FileNotFoundError("File error"),
            InvalidIfcFileError("IFC error"),
            QueryExecutionError("Query error"),
            ConfigurationError("Config error"),
        ]

        for exception in exceptions_to_test:

            def raise_exception():
                raise exception

            # Should be caught by base exception handler
            with pytest.raises(IfcPeekError):
                raise_exception()

    def test_exception_chaining(self):
        """Test exception chaining with from clause."""
        original_error = ValueError("Original error")

        try:
            raise FileNotFoundError("File not found") from original_error
        except FileNotFoundError as e:
            assert e.__cause__ is original_error
            assert str(e) == "File not found"
            assert str(e.__cause__) == "Original error"

    def test_exception_context_preservation(self):
        """Test that exception context is preserved."""

        def inner_function():
            raise ValueError("Inner error")

        def outer_function():
            try:
                inner_function()
            except ValueError:
                raise InvalidIfcFileError("Outer error")

        try:
            outer_function()
        except InvalidIfcFileError as e:
            # Exception context should be preserved
            assert e.__context__ is not None
            assert isinstance(e.__context__, ValueError)
            assert str(e.__context__) == "Inner error"

    def test_custom_exception_attributes(self):
        """Test that custom exceptions can have additional attributes."""

        class CustomIfcError(IfcPeekError):
            def __init__(self, message, error_code=None):
                super().__init__(message)
                self.error_code = error_code

        error = CustomIfcError("Custom error", error_code=404)
        assert str(error) == "Custom error"
        assert error.error_code == 404
        assert isinstance(error, IfcPeekError)


class TestExceptionMessages:
    """Test exception message formatting and content."""

    def test_empty_message(self):
        """Test exceptions with empty messages."""
        error = IfcPeekError("")
        assert str(error) == ""

    def test_none_message(self):
        """Test exceptions with None message."""
        error = IfcPeekError(None)
        assert str(error) == "None"

    def test_multi_line_message(self):
        """Test exceptions with multi-line messages."""
        message = "Line 1\nLine 2\nLine 3"
        error = IfcPeekError(message)
        assert str(error) == message
        assert "\n" in str(error)

    def test_unicode_message(self):
        """Test exceptions with Unicode messages."""
        unicode_message = "Error: 文件未找到 (File not found)"
        error = FileNotFoundError(unicode_message)
        assert str(error) == unicode_message

    def test_formatted_message(self):
        """Test exceptions with formatted messages."""
        filename = "test.ifc"
        message = f"File '{filename}' not found"
        error = FileNotFoundError(message)
        assert str(error) == message
        assert filename in str(error)
