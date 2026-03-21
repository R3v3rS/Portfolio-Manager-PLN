from __future__ import annotations

"""Canonical JSON response helpers for the backend API.

Contract:
- Successful responses should be wrapped as: {"payload": ...}
- Error responses should be wrapped as:
  {"error": {"code": "...", "message": "...", "details": {...}}}

Migration strategy:
- These helpers and the global exception handlers establish the target contract.
- Existing endpoints are intentionally NOT rewritten in bulk yet, so legacy success
  and error shapes can continue to work during the migration window.
- Endpoint-by-endpoint adoption can happen incrementally without breaking current
  frontend compatibility or existing tests.
"""

from typing import Any, TypedDict

from flask import jsonify


class ApiErrorDetails(TypedDict, total=False):
    missing_symbols: list[str]
    field: str


class ApiErrorBody(TypedDict, total=False):
    code: str
    message: str
    details: ApiErrorDetails | dict[str, Any]


class ApiErrorEnvelope(TypedDict):
    error: ApiErrorBody


class ApiSuccessEnvelope(TypedDict):
    payload: Any


class SymbolMappingDTO(TypedDict):
    id: int
    symbol_input: str
    ticker: str
    currency: str | None
    created_at: str | None


class SymbolMappingMutationResultDTO(TypedDict, total=False):
    message: str
    success: bool


class XtbImportResultDTO(TypedDict, total=False):
    success: bool
    message: str
    missing_symbols: list[str]


class LoanMutationResultDTO(TypedDict):
    id: int
    message: str


def success_response(payload: Any, status: int = 200):
    """Return the canonical success envelope."""
    envelope: ApiSuccessEnvelope = {'payload': payload}
    return jsonify(envelope), status



def error_response(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    status: int = 400,
):
    """Return the canonical error envelope.

    `details` stays optional for callers, but the serialized API contract always
    includes a `details` object so clients can rely on a stable schema.
    """
    error: ApiErrorBody = {
        'code': code,
        'message': message,
        'details': details or {},
    }

    envelope: ApiErrorEnvelope = {'error': error}
    return jsonify(envelope), status
