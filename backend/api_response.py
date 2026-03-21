from __future__ import annotations

from typing import Any, TypedDict

from flask import jsonify


class ApiErrorDetails(TypedDict, total=False):
    missing_symbols: list[str]
    field: str


class ApiErrorBody(TypedDict, total=False):
    message: str
    code: str
    details: ApiErrorDetails | dict[str, Any]


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


class ApiErrorEnvelope(TypedDict):
    error: ApiErrorBody


class ApiSuccessEnvelope(TypedDict):
    payload: Any



def success_response(payload: Any, status_code: int = 200):
    envelope: ApiSuccessEnvelope = {'payload': payload}
    return jsonify(envelope), status_code



def error_response(
    message: str,
    *,
    status_code: int = 400,
    code: str | None = None,
    details: dict[str, Any] | None = None,
):
    error: ApiErrorBody = {'message': message}
    if code:
        error['code'] = code
    if details:
        error['details'] = details

    envelope: ApiErrorEnvelope = {'error': error}
    return jsonify(envelope), status_code
