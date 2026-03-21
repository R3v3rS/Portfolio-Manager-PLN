import pandas as pd
from flask import request

from portfolio_service import PortfolioService
from routes_portfolio_base import portfolio_bp
from validators.request_models import validate_xtb_import_file
from validators.responses import error_response, success_response


@portfolio_bp.route('/<int:portfolio_id>/import/xtb', methods=['POST'])
def import_xtb_csv(portfolio_id):
    file = validate_xtb_import_file(request.files.get('file'))

    df = pd.read_csv(file)
    result = PortfolioService.import_xtb_csv(portfolio_id, df)
    if not result['success']:
        return error_response(
            'Import failed',
            status_code=400,
            code='validation_error',
            details=result,
        )
    return success_response(result, message='Import successful')
