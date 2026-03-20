import pandas as pd
from flask import jsonify, request

from portfolio_service import PortfolioService
from routes_portfolio_base import portfolio_bp


@portfolio_bp.route('/<int:portfolio_id>/import/xtb', methods=['POST'])
def import_xtb_csv(portfolio_id):
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    try:
        df = pd.read_csv(file)
        result = PortfolioService.import_xtb_csv(portfolio_id, df)
        if not result['success']:
            return jsonify(result), 400
        return jsonify({'message': 'Import successful', **result}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400
