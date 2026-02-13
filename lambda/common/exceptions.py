"""Shared exceptions and error handling utilities for Lambda functions."""

from typing import Type, Dict
from datetime import datetime, UTC


class LambdaError(Exception):
    """Base exception for all Lambda function errors."""

    pass


class ConfigurationError(LambdaError):
    """Raised when there's a configuration error."""

    pass


class APIError(LambdaError):
    """Raised when API requests fail."""

    pass


class DataValidationError(LambdaError):
    """Raised when data validation fails."""

    pass


class DataProcessingError(LambdaError):
    """Raised when data processing fails."""

    pass


class S3OperationError(LambdaError):
    """Raised when S3 operations fail."""

    pass


ERROR_STATUS_CODES: Dict[Type[LambdaError], int] = {
    ConfigurationError: 400,
    APIError: 503,
    DataValidationError: 422,
    DataProcessingError: 422,
    S3OperationError: 503,
}
ERROR_STATUS_CODE_NAMES: Dict[str, int] = {
    "ConfigurationError": 400,
    "ValidationError": 400,
    "APIError": 503,
    "DataValidationError": 422,
    "DataProcessingError": 422,
    "S3OperationError": 503,
}


def get_current_time() -> datetime:
    """Get current datetime in UTC timezone."""
    return datetime.now(UTC)
