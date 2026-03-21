from __future__ import annotations

from typing import Any


class ApiError(Exception):
    """Raised for application-defined API errors with explicit status/code."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details


class ValidationError(Exception):
    """Raised when client input fails validation."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(Exception):
    """Raised when a requested domain resource does not exist."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details
