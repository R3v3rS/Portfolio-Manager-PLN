import pandas as pd
from flask import request

from api_response import error_response, success_response
from portfolio_service import PortfolioService
from routes_portfolio_base import portfolio_bp


@portfolio_bp.route('/<int:portfolio_id>/import/xtb', methods=['POST'])
def import_xtb_csv(portfolio_id):
    if 'file' not in request.files:
        return error_response('No file part', status_code=400, code='file_missing')

    file = request.files['file']
    if file.filename == '':
        return error_response('No selected file', status_code=400, code='file_name_missing')

    try:
        df = pd.read_csv(file)
        result = PortfolioService.import_xtb_csv(portfolio_id, df)
        if not result['success']:
            return error_response(
                'Import failed.',
                status_code=400,
                code='xtb_import_failed',
                details={'missing_symbols': result.get('missing_symbols', [])},
            )
        return success_response({'message': 'Import successful', **result}, 200)
    except Exception as e:
        return error_response(str(e), status_code=400, code='xtb_import_invalid_csv')
