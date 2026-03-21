from __future__ import annotations

"""Backward-compatible shim for legacy imports.

New code should import from `api.response`.
Existing routes still import this module, so we keep the old call signature while
routing responses through the new canonical helpers.
"""

from typing import Any

from api.response import (
    ApiErrorBody,
    ApiErrorDetails,
    ApiErrorEnvelope,
    ApiSuccessEnvelope,
    LoanMutationResultDTO,
    SymbolMappingDTO,
    SymbolMappingMutationResultDTO,
    XtbImportResultDTO,
    error_response as _canonical_error_response,
    success_response as _canonical_success_response,
)


def success_response(payload: Any, status_code: int = 200):
    return _canonical_success_response(payload, status=status_code)



def error_response(
    message: str,
    *,
    status_code: int = 400,
    code: str | None = None,
    details: dict[str, Any] | None = None,
):
    # Compatibility layer: legacy callers often passed only a message and optional
    # status/code kwargs. The new canonical helper requires an explicit string code,
    # so we derive a stable fallback here until routes are migrated individually.
    error_code = code or f'http_{status_code}_error'
    return _canonical_error_response(error_code, message, details=details, status=status_code)
