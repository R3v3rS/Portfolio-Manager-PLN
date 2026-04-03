from flask import Blueprint, current_app, request
import os

from api.exceptions import NotFoundError, ValidationError

portfolio_bp = Blueprint('portfolio', __name__)


def is_admin_debug_request() -> bool:
    admin_token = os.getenv('PORTFOLIO_ADMIN_TOKEN')
    if admin_token:
        return request.headers.get('X-Admin-Token') == admin_token
    return bool(current_app.debug)


def require_json_body() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError('Invalid JSON body')
    return data


def require_field(data: dict, field: str):
    if field not in data:
        raise ValidationError(f'Missing field: {field}', details={'field': field})
    return data[field]


def require_non_empty_string(data: dict, field: str) -> str:
    value = require_field(data, field)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f'Field {field} must be a non-empty string', details={'field': field})
    return value.strip()


def optional_string(data: dict, field: str) -> str | None:
    if field not in data or data[field] is None:
        return None
    value = data[field]
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f'Field {field} must be a non-empty string', details={'field': field})
    return value.strip()


def require_positive_int(data: dict, field: str) -> int:
    value = require_field(data, field)
    if isinstance(value, bool):
        raise ValidationError(f'Field {field} must be a positive integer', details={'field': field})
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f'Field {field} must be a positive integer', details={'field': field}) from exc
    if parsed <= 0:
        raise ValidationError(f'Field {field} must be a positive integer', details={'field': field})
    return parsed


def optional_positive_int(data: dict, field: str) -> int | None:
    if field not in data or data[field] is None:
        return None
    value = data[field]
    if isinstance(value, bool):
        raise ValidationError(f'Field {field} must be a positive integer', details={'field': field})
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f'Field {field} must be a positive integer', details={'field': field}) from exc
    if parsed <= 0:
        raise ValidationError(f'Field {field} must be a positive integer', details={'field': field})
    return parsed


def require_number(data: dict, field: str, *, positive: bool = False, non_negative: bool = False) -> float:
    value = require_field(data, field)
    if isinstance(value, bool):
        raise ValidationError(f'Field {field} must be a number', details={'field': field})
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f'Field {field} must be a number', details={'field': field}) from exc

    if positive and parsed <= 0:
        raise ValidationError(f'Field {field} must be greater than zero', details={'field': field})
    if non_negative and parsed < 0:
        raise ValidationError(f'Field {field} must be zero or greater', details={'field': field})
    return parsed


def optional_number(data: dict, field: str, *, default: float = 0.0, non_negative: bool = False) -> float:
    if field not in data or data[field] is None:
        return default
    return require_number(data, field, non_negative=non_negative)


def optional_bool(data: dict, field: str, *, default: bool = False) -> bool:
    if field not in data:
        return default
    value = data[field]
    if not isinstance(value, bool):
        raise ValidationError(f'Field {field} must be a boolean', details={'field': field})
    return value


def raise_portfolio_validation_error(error: ValueError):
    message = str(error)
    if message == 'Portfolio not found':
        raise NotFoundError(message) from error
    raise ValidationError(message) from error
