import pandas as pd
from flask import request

from api.exceptions import ApiError, NotFoundError, ValidationError
from api.response import success_response
from import_staging_service import ImportBookingError, ImportRowSkipError, ImportStagingService
from portfolio_service import PortfolioService
from routes_portfolio_base import portfolio_bp


@portfolio_bp.route('/<int:portfolio_id>/import/xtb', methods=['POST'])
def import_xtb_csv(portfolio_id):
    # Sprawdzenie czy mamy plik (pierwszy krok) lub potwierdzenie duplikatów (drugi krok)
    confirmed_hashes = request.json.get('confirmed_hashes') if request.is_json else None
    
    # Jeśli to potwierdzenie, musimy mieć dane w sesji lub przesłane ponownie? 
    # W aktualnej architekturze frontend wysyła plik ponownie razem z confirmed_hashes 
    # LUB musimy zapisać plik tymczasowo.
    # Najprościej: frontend wysyła plik ponownie wraz z confirmed_hashes w form-data.
    
    confirmed_hashes_raw = request.form.get('confirmed_hashes')
    sub_portfolio_id = request.form.get('sub_portfolio_id', type=int)
    
    if confirmed_hashes_raw:
        try:
            import json
            confirmed_hashes = json.loads(confirmed_hashes_raw)
        except:
            confirmed_hashes = []

    if 'file' not in request.files:
        raise ValidationError('No file part', details={'field': 'file'})

    file = request.files['file']
    if file.filename == '':
        raise ValidationError('No selected file', details={'field': 'file'})

    try:
        df = pd.read_csv(file)
    except (pd.errors.ParserError, UnicodeDecodeError, ValueError) as error:
        raise ApiError(
            'xtb_import_invalid_csv',
            str(error),
            status=400,
            details={},
        ) from error

    result = PortfolioService.import_xtb_csv(portfolio_id, df, confirmed_hashes=confirmed_hashes, sub_portfolio_id=sub_portfolio_id)
    if not result['success']:
        raise ApiError(
            'IMPORT_VALIDATION_ERROR',
            'Missing symbol mappings',
            details={'missing_symbols': result.get('missing_symbols', [])},
            status=400,
        )

    # Obsługa statusu warning (duplikaty)
    if result.get('status') == 'warning':
        return success_response({
            'message': 'Potential duplicates found',
            'status': 'warning',
            'potential_conflicts': result.get('potential_conflicts', []),
            'missing_symbols': []
        })

    return success_response({'message': 'Import successful', **result})


@portfolio_bp.route('/import/staging', methods=['POST'])
def import_with_staging():
    if 'file' not in request.files:
        raise ValidationError('No file part', details={'field': 'file'})

    file = request.files['file']
    if file.filename == '':
        raise ValidationError('No selected file', details={'field': 'file'})

    portfolio_id = request.form.get('portfolio_id', type=int)
    if portfolio_id is None:
        raise ValidationError('portfolio_id is required', details={'field': 'portfolio_id'})

    sub_portfolio_id = request.form.get('sub_portfolio_id', type=int)
    mode = (request.form.get('mode') or 'staging').strip().lower()
    if mode not in {'staging', 'direct'}:
        raise ValidationError("mode must be one of: 'staging', 'direct'", details={'field': 'mode'})

    try:
        df = pd.read_csv(file)
    except (pd.errors.ParserError, UnicodeDecodeError, ValueError) as error:
        raise ApiError(
            'xtb_import_invalid_csv',
            str(error),
            status=400,
            details={},
        ) from error

    if mode == 'direct':
        try:
            result = PortfolioService.import_xtb_csv(
                portfolio_id,
                df,
                confirmed_hashes=None,
                sub_portfolio_id=sub_portfolio_id,
            )
        except ValueError as error:
            raise ApiError('IMPORT_VALIDATION_ERROR', str(error), status=400) from error
        if not result.get('success'):
            raise ApiError(
                'IMPORT_VALIDATION_ERROR',
                'Missing symbol mappings',
                details={'missing_symbols': result.get('missing_symbols', [])},
                status=400,
            )
        return success_response(result)

    try:
        result = ImportStagingService.create_session(
            portfolio_id=portfolio_id,
            df=df,
            sub_portfolio_id=sub_portfolio_id,
            source_file=file.filename,
        )
    except ValueError as error:
        raise ApiError('IMPORT_VALIDATION_ERROR', str(error), status=400) from error
    return success_response(result)


@portfolio_bp.route('/import/staging/<session_id>', methods=['GET'])
def get_import_staging_session(session_id):
    try:
        result = ImportStagingService.get_session(session_id)
        return success_response(result)
    except ValueError as error:
        raise NotFoundError(str(error)) from error


@portfolio_bp.route('/import/staging/<session_id>/rows/<int:row_id>/assign', methods=['PUT'])
def assign_import_staging_row(session_id, row_id):
    payload = request.get_json(silent=True) or {}
    raw_target_sub_portfolio_id = payload.get('target_sub_portfolio_id')
    if raw_target_sub_portfolio_id is None:
        target_sub_portfolio_id = None
    else:
        try:
            val = int(raw_target_sub_portfolio_id)
            if val != float(raw_target_sub_portfolio_id):
                raise ValueError()
            if val <= 0:
                raise ValueError()
            target_sub_portfolio_id = val
        except (TypeError, ValueError) as error:
            raise ApiError(
                'invalid_sub_portfolio',
                'target_sub_portfolio_id must be a positive integer',
                status=422,
                details={'field': 'target_sub_portfolio_id'},
            ) from error

    try:
        result = ImportStagingService.assign_row(
            session_id=session_id,
            row_id=row_id,
            target_sub_portfolio_id=target_sub_portfolio_id,
        )
        return success_response(result)
    except ValueError as error:
        message = str(error)
        if 'sub-portfolio' in message.lower():
            raise ApiError(
                'invalid_sub_portfolio',
                message,
                status=422,
                details={'field': 'target_sub_portfolio_id'},
            ) from error
        raise NotFoundError(message) from error
    except ImportRowSkipError as error:
        raise ApiError('row_skipped', str(error), status=409) from error


@portfolio_bp.route('/import/staging/<session_id>/assign-all', methods=['PUT'])
def assign_all_import_staging_rows(session_id):
    payload = request.get_json(silent=True) or {}
    raw_target_sub_portfolio_id = payload.get('target_sub_portfolio_id')
    if raw_target_sub_portfolio_id is None:
        target_sub_portfolio_id = None
    else:
        try:
            val = int(raw_target_sub_portfolio_id)
            if val != float(raw_target_sub_portfolio_id):
                raise ValueError()
            if val <= 0:
                raise ValueError()
            target_sub_portfolio_id = val
        except (TypeError, ValueError) as error:
            raise ApiError(
                'invalid_sub_portfolio',
                'target_sub_portfolio_id must be a positive integer',
                status=422,
                details={'field': 'target_sub_portfolio_id'},
            ) from error

    try:
        result = ImportStagingService.assign_all(
            session_id=session_id,
            target_sub_portfolio_id=target_sub_portfolio_id,
        )
        return success_response(result)
    except ValueError as error:
        message = str(error)
        if 'sub-portfolio' in message.lower():
            raise ApiError(
                'invalid_sub_portfolio',
                message,
                status=422,
                details={'field': 'target_sub_portfolio_id'},
            ) from error
        raise NotFoundError(message) from error


@portfolio_bp.route('/import/staging/<session_id>/rows/<int:row_id>', methods=['DELETE'])
def reject_import_staging_row(session_id, row_id):
    try:
        result = ImportStagingService.reject_row(session_id=session_id, row_id=row_id)
        return success_response(result)
    except ValueError as error:
        raise NotFoundError(str(error)) from error


@portfolio_bp.route('/import/staging/<session_id>/book', methods=['POST'])
def book_import_staging_session(session_id):
    payload = request.get_json(silent=True) or {}
    confirmed_row_ids = payload.get('confirmed_row_ids')
    if confirmed_row_ids is not None and not isinstance(confirmed_row_ids, list):
        raise ValidationError('confirmed_row_ids must be a list', details={'field': 'confirmed_row_ids'})

    try:
        result = ImportStagingService.book_session(session_id=session_id, confirmed_row_ids=confirmed_row_ids)
        return success_response(result)
    except ImportBookingError as error:
        raise ApiError(
            'BOOKING_ERROR',
            str(error),
            details={'row_errors': error.row_errors},
            status=422,
        ) from error
    except ValueError as error:
        raise NotFoundError(str(error)) from error


@portfolio_bp.route('/import/staging/<session_id>', methods=['DELETE'])
def delete_import_staging_session(session_id):
    result = ImportStagingService.delete_session(session_id=session_id)
    return success_response(result)
