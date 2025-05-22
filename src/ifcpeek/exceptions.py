"""Custom exceptions with better error reporting and context."""


class IfcPeekError(Exception):
    """Base exception for ifcpeek errors with context."""

    def __init__(self, message, context=None):
        super().__init__(message)
        self.context = context or {}

    def __str__(self):
        base_msg = super().__str__()
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{base_msg} [Context: {context_str}]"
        return base_msg


class FileNotFoundError(IfcPeekError):
    """FileNotFoundError with path context."""

    def __init__(self, message, file_path=None):
        context = {"file_path": file_path} if file_path else {}
        super().__init__(message, context)


class InvalidIfcFileError(IfcPeekError):
    """InvalidIfcFileError with file analysis context."""

    def __init__(self, message, file_path=None, file_size=None, error_type=None):
        context = {}
        if file_path:
            context["file_path"] = file_path
        if file_size is not None:
            context["file_size"] = file_size
        if error_type:
            context["error_type"] = error_type
        super().__init__(message, context)


class QueryExecutionError(IfcPeekError):
    """QueryExecutionError with query context."""

    def __init__(self, message, query=None, model_schema=None):
        context = {}
        if query:
            context["query"] = query
        if model_schema:
            context["model_schema"] = model_schema
        super().__init__(message, context)


class ConfigurationError(IfcPeekError):
    """ConfigurationError with system context."""

    def __init__(self, message, config_path=None, system_info=None):
        context = {}
        if config_path:
            context["config_path"] = config_path
        if system_info:
            context.update(system_info)
        super().__init__(message, context)
