from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

import requests

try:
    from yfinance.exceptions import YFRateLimitError  # type: ignore
except Exception:  # pragma: no cover - defensive import for older yfinance versions
    YFRateLimitError = None


class UpstreamErrorCode(str, Enum):
    NETWORK_TIMEOUT = 'NETWORK_TIMEOUT'
    RATE_LIMIT = 'RATE_LIMIT'
    AUTH_OR_PERMISSION = 'AUTH_OR_PERMISSION'
    UPSTREAM_SCHEMA_CHANGE = 'UPSTREAM_SCHEMA_CHANGE'
    SYMBOL_NOT_FOUND = 'SYMBOL_NOT_FOUND'
    UNKNOWN_UPSTREAM_ERROR = 'UNKNOWN_UPSTREAM_ERROR'


@dataclass(frozen=True)
class UpstreamErrorContext:
    provider: str
    symbol: str | None = None
    interval: str | None = None
    operation: str | None = None


@dataclass(frozen=True)
class ClassifiedUpstreamError:
    code: UpstreamErrorCode
    user_message: str
    technical_message: str


def _status_code_from_exception(exception: Exception) -> int | None:
    response = getattr(exception, 'response', None)
    status_code = getattr(response, 'status_code', None)
    if isinstance(status_code, int):
        return status_code
    return None


def _safe_exception_text(exception: Exception) -> str:
    text = str(exception).strip()
    if not text:
        return exception.__class__.__name__
    return text


def _looks_like_symbol_not_found(exception_text: str) -> bool:
    normalized = exception_text.lower()
    patterns = (
        'possibly delisted',
        'no timezone found',
        'not found',
        '404',
        'no data found',
        'invalid symbol',
        'symbol may be delisted',
    )
    return any(pattern in normalized for pattern in patterns)


def _looks_like_schema_change(exception: Exception, exception_text: str) -> bool:
    if isinstance(exception, (KeyError, IndexError)):
        return True

    normalized = exception_text.lower()
    patterns = (
        'missing column',
        'columns',
        'jsondecodeerror',
        'json decode',
        'unexpected format',
        'malformed response',
        'not in index',
        'cannot index',
    )
    return any(pattern in normalized for pattern in patterns)


def classify_yfinance_error(
    exception: Exception,
    context: UpstreamErrorContext,
) -> UpstreamErrorCode:
    """Map yfinance/requests exceptions into stable internal categories."""
    exception_text = _safe_exception_text(exception)
    status_code = _status_code_from_exception(exception)

    if isinstance(exception, (requests.Timeout, requests.ConnectTimeout, requests.ReadTimeout, TimeoutError)):
        return UpstreamErrorCode.NETWORK_TIMEOUT

    if YFRateLimitError is not None and isinstance(exception, YFRateLimitError):
        return UpstreamErrorCode.RATE_LIMIT

    if status_code == 429 or 'rate limit' in exception_text.lower() or 'too many requests' in exception_text.lower():
        return UpstreamErrorCode.RATE_LIMIT

    if isinstance(exception, PermissionError) or status_code in (401, 403):
        return UpstreamErrorCode.AUTH_OR_PERMISSION

    if _looks_like_symbol_not_found(exception_text):
        return UpstreamErrorCode.SYMBOL_NOT_FOUND

    if _looks_like_schema_change(exception, exception_text):
        return UpstreamErrorCode.UPSTREAM_SCHEMA_CHANGE

    return UpstreamErrorCode.UNKNOWN_UPSTREAM_ERROR


def _user_message_for_code(code: UpstreamErrorCode, context: UpstreamErrorContext) -> str:
    symbol_label = context.symbol or 'wybranego instrumentu'

    if code == UpstreamErrorCode.NETWORK_TIMEOUT:
        return f'Nie udało się pobrać danych dla {symbol_label} z powodu limitu czasu połączenia.'
    if code == UpstreamErrorCode.RATE_LIMIT:
        return 'Dostawca danych chwilowo ogranicza liczbę zapytań. Spróbuj ponownie za chwilę.'
    if code == UpstreamErrorCode.AUTH_OR_PERMISSION:
        return 'Brak uprawnień do pobrania danych od dostawcy.'
    if code == UpstreamErrorCode.UPSTREAM_SCHEMA_CHANGE:
        return 'Dane od dostawcy mają nieoczekiwany format. Zespół został poinformowany.'
    if code == UpstreamErrorCode.SYMBOL_NOT_FOUND:
        return f'Nie znaleziono symbolu {symbol_label} u dostawcy danych.'
    return 'Wystąpił nieoczekiwany błąd podczas pobierania danych rynkowych.'


def build_yfinance_error(
    exception: Exception,
    context: UpstreamErrorContext,
) -> ClassifiedUpstreamError:
    code = classify_yfinance_error(exception, context)
    user_message = _user_message_for_code(code, context)
    technical_message = (
        f'provider={context.provider} operation={context.operation or "unknown"} '
        f'symbol={context.symbol or "n/a"} interval={context.interval or "n/a"} '
        f'code={code.value} exception_type={exception.__class__.__name__} '
        f'exception={_safe_exception_text(exception)}'
    )

    return ClassifiedUpstreamError(
        code=code,
        user_message=user_message,
        technical_message=technical_message,
    )
