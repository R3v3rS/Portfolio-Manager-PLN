import pandas as pd
from flask import request

from api.exceptions import ApiError, ValidationError
from api.response import success_response
from portfolio_service import PortfolioService
from routes_portfolio_base import portfolio_bp


@portfolio_bp.route('/<int:portfolio_id>/import/xtb', methods=['POST'])
def import_xtb_csv(portfolio_id):
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

    result = PortfolioService.import_xtb_csv(portfolio_id, df)
    if not result['success']:
        raise ApiError(
            'IMPORT_VALIDATION_ERROR',
            'Missing symbol mappings',
            details={'missing_symbols': result.get('missing_symbols', [])},
            status=400,
        )

    return success_response({'message': 'Import successful', **result})
