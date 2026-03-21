from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .errors import ValidationError

PORTFOLIO_ACCOUNT_TYPES = {'STANDARD', 'IKE', 'IKZE', 'PPK', 'SAVINGS'}
LOAN_INSTALLMENT_TYPES = {'EQUAL', 'DECREASING'}
LOAN_OVERPAYMENT_TYPES = {'REDUCE_TERM', 'REDUCE_INSTALLMENT'}
DATE_FORMATS = ('%Y-%m-%d', '%Y-%m-%d %H:%M:%S')


@dataclass
class ValidationContext:
    payload: dict[str, Any]
    errors: list[dict[str, str]]


def _ensure_dict(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValidationError([
            {'field': 'body', 'message': 'Request body must be a JSON object.'}
        ], message='Invalid request body')
    return payload


def _add_error(ctx: ValidationContext, field: str, message: str):
    ctx.errors.append({'field': field, 'message': message})


def _get_required(ctx: ValidationContext, field: str):
    value = ctx.payload.get(field)
    if value is None:
        _add_error(ctx, field, 'This field is required.')
        return None
    return value


def _parse_int(ctx: ValidationContext, field: str, *, required=True, minimum: int | None = None):
    raw = _get_required(ctx, field) if required else ctx.payload.get(field)
    if raw is None:
        return None
    if isinstance(raw, bool):
        _add_error(ctx, field, 'Must be an integer.')
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        _add_error(ctx, field, 'Must be an integer.')
        return None
    if minimum is not None and value < minimum:
        _add_error(ctx, field, f'Must be greater than or equal to {minimum}.')
    return value


def _parse_float(ctx: ValidationContext, field: str, *, required=True, minimum: float | None = None, allow_zero=True):
    raw = _get_required(ctx, field) if required else ctx.payload.get(field)
    if raw is None:
        return None
    if isinstance(raw, bool):
        _add_error(ctx, field, 'Must be a number.')
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        _add_error(ctx, field, 'Must be a number.')
        return None
    if minimum is not None and value < minimum:
        _add_error(ctx, field, f'Must be greater than or equal to {minimum}.')
    if not allow_zero and value == 0:
        _add_error(ctx, field, 'Must be greater than 0.')
    return value


def _parse_string(ctx: ValidationContext, field: str, *, required=True, allowed: set[str] | None = None, min_length: int = 1):
    raw = _get_required(ctx, field) if required else ctx.payload.get(field)
    if raw is None:
        return None
    if not isinstance(raw, str):
        _add_error(ctx, field, 'Must be a string.')
        return None
    value = raw.strip()
    if len(value) < min_length:
        _add_error(ctx, field, 'Must not be empty.')
        return None
    if allowed is not None and value not in allowed:
        _add_error(ctx, field, f"Must be one of: {', '.join(sorted(allowed))}.")
    return value


def _parse_date(ctx: ValidationContext, field: str, *, required=False):
    raw = _get_required(ctx, field) if required else ctx.payload.get(field)
    if raw is None:
        return None
    if not isinstance(raw, str):
        _add_error(ctx, field, 'Must be a date string in YYYY-MM-DD or YYYY-MM-DD HH:MM:SS format.')
        return None
    value = raw.strip()
    for fmt in DATE_FORMATS:
        try:
            datetime.strptime(value, fmt)
            return value
        except ValueError:
            continue
    _add_error(ctx, field, 'Must be a date string in YYYY-MM-DD or YYYY-MM-DD HH:MM:SS format.')
    return None


def _parse_bool(ctx: ValidationContext, field: str, *, required=False):
    raw = _get_required(ctx, field) if required else ctx.payload.get(field)
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    _add_error(ctx, field, 'Must be a boolean.')
    return None


def _raise_if_errors(ctx: ValidationContext):
    if ctx.errors:
        raise ValidationError(ctx.errors)


def validate_portfolio_create(payload: Any) -> dict[str, Any]:
    ctx = ValidationContext(payload=_ensure_dict(payload), errors=[])
    data = {
        'name': _parse_string(ctx, 'name'),
        'initial_cash': _parse_float(ctx, 'initial_cash', required=False, minimum=0.0),
        'account_type': _parse_string(ctx, 'account_type', required=False, allowed=PORTFOLIO_ACCOUNT_TYPES),
        'created_at': _parse_date(ctx, 'created_at', required=False),
    }
    _raise_if_errors(ctx)
    data['initial_cash'] = 0.0 if data['initial_cash'] is None else data['initial_cash']
    data['account_type'] = data['account_type'] or 'STANDARD'
    return data


def validate_portfolio_trade(payload: Any) -> dict[str, Any]:
    ctx = ValidationContext(payload=_ensure_dict(payload), errors=[])
    data = {
        'portfolio_id': _parse_int(ctx, 'portfolio_id', minimum=1),
        'ticker': _parse_string(ctx, 'ticker'),
        'quantity': _parse_float(ctx, 'quantity', minimum=0.0, allow_zero=False),
        'price': _parse_float(ctx, 'price', minimum=0.0, allow_zero=False),
        'date': _parse_date(ctx, 'date', required=False),
        'commission': _parse_float(ctx, 'commission', required=False, minimum=0.0),
        'auto_fx_fees': _parse_bool(ctx, 'auto_fx_fees', required=False),
    }
    _raise_if_errors(ctx)
    data['commission'] = 0.0 if data['commission'] is None else data['commission']
    data['auto_fx_fees'] = False if data['auto_fx_fees'] is None else data['auto_fx_fees']
    return data


def validate_account_transfer(payload: Any) -> dict[str, Any]:
    ctx = ValidationContext(payload=_ensure_dict(payload), errors=[])
    data = {
        'from_account_id': _parse_int(ctx, 'from_account_id', minimum=1),
        'to_account_id': _parse_int(ctx, 'to_account_id', minimum=1),
        'amount': _parse_float(ctx, 'amount', minimum=0.0, allow_zero=False),
        'description': _parse_string(ctx, 'description', required=False),
        'date': _parse_date(ctx, 'date', required=False),
        'target_envelope_id': _parse_int(ctx, 'target_envelope_id', required=False, minimum=1),
        'source_envelope_id': _parse_int(ctx, 'source_envelope_id', required=False, minimum=1),
    }
    if data['from_account_id'] is not None and data['to_account_id'] is not None and data['from_account_id'] == data['to_account_id']:
        _add_error(ctx, 'to_account_id', 'Must be different from from_account_id.')
    _raise_if_errors(ctx)
    data['description'] = data['description'] or 'Transfer'
    return data


def validate_budget_portfolio_transfer(payload: Any, *, direction: str) -> dict[str, Any]:
    ctx = ValidationContext(payload=_ensure_dict(payload), errors=[])
    data = {
        'budget_account_id': _parse_int(ctx, 'budget_account_id', minimum=1),
        'portfolio_id': _parse_int(ctx, 'portfolio_id', minimum=1),
        'amount': _parse_float(ctx, 'amount', minimum=0.0, allow_zero=False),
        'envelope_id': _parse_int(ctx, 'envelope_id', required=False, minimum=1),
        'description': _parse_string(ctx, 'description', required=False),
        'date': _parse_date(ctx, 'date', required=False),
    }
    _raise_if_errors(ctx)
    default_description = 'Transfer to Investments' if direction == 'to_portfolio' else 'Wypłata z portfela inwestycyjnego'
    data['description'] = data['description'] or default_description
    return data


def validate_loan_create(payload: Any) -> dict[str, Any]:
    ctx = ValidationContext(payload=_ensure_dict(payload), errors=[])
    data = {
        'name': _parse_string(ctx, 'name'),
        'original_amount': _parse_float(ctx, 'original_amount', minimum=0.0, allow_zero=False),
        'duration_months': _parse_int(ctx, 'duration_months', minimum=1),
        'start_date': _parse_date(ctx, 'start_date', required=True),
        'installment_type': _parse_string(ctx, 'installment_type', allowed=LOAN_INSTALLMENT_TYPES),
        'initial_rate': _parse_float(ctx, 'initial_rate', minimum=0.0),
        'category': _parse_string(ctx, 'category', required=False),
    }
    _raise_if_errors(ctx)
    data['category'] = data['category'] or 'GOTOWKOWY'
    return data


def validate_loan_overpayment(payload: Any) -> dict[str, Any]:
    ctx = ValidationContext(payload=_ensure_dict(payload), errors=[])
    data = {
        'amount': _parse_float(ctx, 'amount', minimum=0.0, allow_zero=False),
        'date': _parse_date(ctx, 'date', required=True),
        'type': _parse_string(ctx, 'type', required=False, allowed=LOAN_OVERPAYMENT_TYPES),
    }
    _raise_if_errors(ctx)
    data['type'] = data['type'] or 'REDUCE_TERM'
    return data


def validate_xtb_import_file(file_storage):
    errors = []
    if file_storage is None:
        errors.append({'field': 'file', 'message': 'File is required.'})
    else:
        filename = (file_storage.filename or '').strip()
        if not filename:
            errors.append({'field': 'file', 'message': 'Filename must not be empty.'})
        elif not filename.lower().endswith('.csv'):
            errors.append({'field': 'file', 'message': 'Only CSV files are supported.'})
    if errors:
        raise ValidationError(errors, message='Invalid import request')
    return file_storage
