import pandas as pd
from flask import request

from api.exceptions import ApiError, ValidationError
from api.response import success_response
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

    result = PortfolioService.import_xtb_csv(portfolio_id, df, confirmed_hashes=confirmed_hashes)
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
