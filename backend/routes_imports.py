import pandas as pd
from flask import request

from api.exceptions import ValidationError
from api.response import error_response, success_response
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
    except Exception as error:
        return error_response(
            'xtb_import_invalid_csv',
            str(error),
            details={},
            status=400,
        )

    result = PortfolioService.import_xtb_csv(portfolio_id, df)
    if not result['success']:
        return error_response(
            'IMPORT_VALIDATION_ERROR',
            'Missing symbol mappings',
            details={'missing_symbols': result.get('missing_symbols', [])},
            status=400,
        )

    return success_response({'message': 'Import successful', **result})
