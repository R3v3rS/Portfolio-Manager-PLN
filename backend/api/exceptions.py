from __future__ import annotations

from typing import Any


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
