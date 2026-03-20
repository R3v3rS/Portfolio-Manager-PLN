from flask import jsonify, request

from modules.ppk.ppk_service import PPKService
from routes_portfolio_base import portfolio_bp


@portfolio_bp.route('/ppk/transactions/<int:portfolio_id>', methods=['GET'])
def get_ppk_transactions(portfolio_id):
    try:
        current_price_raw = request.args.get('current_price')
        current_price_data = None
        current_price = None

        if current_price_raw is not None:
            current_price = float(current_price_raw)
        else:
            try:
                current_price_data = PPKService.fetch_current_price()
                current_price = current_price_data['price']
            except Exception:
                current_price_data = None

        transactions = PPKService.get_transactions(portfolio_id)
        summary = PPKService.get_portfolio_summary(portfolio_id, current_price)
        return jsonify({'transactions': transactions, 'summary': summary, 'currentPrice': current_price_data}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@portfolio_bp.route('/ppk/transactions', methods=['POST'])
def add_ppk_transaction():
    data = request.json
    try:
        PPKService.add_transaction(
            data['portfolio_id'],
            data.get('date'),
            data['employeeUnits'],
            data['employerUnits'],
            data['pricePerUnit']
        )
        return jsonify({'message': 'PPK transaction added successfully'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400
