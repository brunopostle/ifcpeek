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
    """Test exception class inheritance and basic functionality."""

    def test_base_exception(self):
        """Test base IfcPeekError functionality."""
        error = IfcPeekError("Test error")
        assert isinstance(error, Exception)
        assert str(error) == "Test error"

    def test_all_exceptions_inherit_from_base(self):
        """Test that all custom exceptions inherit from IfcPeekError."""
        exceptions = [
            FileNotFoundError("File not found"),
            InvalidIfcFileError("Invalid IFC"),
            QueryExecutionError("Query failed"),
            ConfigurationError("Config error"),
        ]

        for exc in exceptions:
            assert isinstance(exc, IfcPeekError)
            assert isinstance(exc, Exception)

    def test_exception_chaining(self):
        """Test exception chaining works correctly."""
        original = ValueError("Original error")

        try:
            raise FileNotFoundError("File not found") from original
        except FileNotFoundError as e:
            assert e.__cause__ is original
            assert str(e) == "File not found"

    def test_catch_base_exception_catches_all(self):
        """Test that catching IfcPeekError catches all custom exceptions."""
        exceptions = [
            FileNotFoundError("File error"),
            InvalidIfcFileError("IFC error"),
            QueryExecutionError("Query error"),
            ConfigurationError("Config error"),
        ]

        for exception in exceptions:
            with pytest.raises(IfcPeekError):
                raise exception
