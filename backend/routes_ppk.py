from flask import request

from api.response import success_response
from modules.ppk.ppk_service import PPKService
from routes_portfolio_base import (
    optional_string,
    portfolio_bp,
    require_json_body,
    require_number,
    require_positive_int,
)


@portfolio_bp.route('/ppk/transactions/<int:portfolio_id>', methods=['GET'])
def get_ppk_transactions(portfolio_id):
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
    return success_response({'transactions': transactions, 'summary': summary, 'currentPrice': current_price_data})


@portfolio_bp.route('/ppk/transactions', methods=['POST'])
def add_ppk_transaction():
    data = require_json_body()
    PPKService.add_transaction(
        require_positive_int(data, 'portfolio_id'),
        optional_string(data, 'date'),
        require_number(data, 'employeeUnits', non_negative=True),
        require_number(data, 'employerUnits', non_negative=True),
        require_number(data, 'pricePerUnit', positive=True),
    )
    return success_response({'message': 'PPK transaction added successfully'}, status=201)


@portfolio_bp.route('/ppk/performance/<int:portfolio_id>', methods=['GET'])
def get_ppk_performance(portfolio_id):
    # Default fund ID for NN PPK 2055
    fund_id = request.args.get('fund_id', '61777738')
    performance = PPKService.compute_performance(portfolio_id, fund_id)
    return success_response(performance)
