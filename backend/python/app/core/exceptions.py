"""Centralized exception types for the ML service."""


class SchedulingError(Exception):
    """Raised when scheduling pipeline encounters a fatal error."""


class ConfigError(Exception):
    """Raised when configuration is invalid or missing."""


class ModelError(Exception):
    """Raised when model inference or loading fails."""


class DataError(Exception):
    """Raised when input data is invalid or insufficient."""
