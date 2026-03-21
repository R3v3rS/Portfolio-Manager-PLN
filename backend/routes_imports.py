import pandas as pd
from flask import jsonify, request

from portfolio_service import PortfolioService
from routes_portfolio_base import portfolio_bp
from validators.request_models import validate_xtb_import_file


@portfolio_bp.route('/<int:portfolio_id>/import/xtb', methods=['POST'])
def import_xtb_csv(portfolio_id):
    file = validate_xtb_import_file(request.files.get('file'))

    df = pd.read_csv(file)
    result = PortfolioService.import_xtb_csv(portfolio_id, df)
    if not result['success']:
        return jsonify(result), 400
    return jsonify({'message': 'Import successful', **result}), 200
