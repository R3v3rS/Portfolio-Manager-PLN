from flask import request

from bond_service import BondService
from portfolio_service import PortfolioService
from routes_portfolio_base import portfolio_bp
from validators.responses import error_response, success_response
from validators.request_models import validate_portfolio_create


@portfolio_bp.route('/limits', methods=['GET'])
def get_tax_limits():
    try:
        limits = PortfolioService.get_tax_limits()
        return success_response({'limits': limits})
    except Exception as e:
        return error_response(str(e), status_code=500, code='internal_server_error')


@portfolio_bp.route('/create', methods=['POST'])
def create_portfolio():
    data = validate_portfolio_create(request.get_json(silent=True))
    portfolio_id = PortfolioService.create_portfolio(
        data['name'],
        data['initial_cash'],
        data['account_type'],
        data.get('created_at')
    )
    return success_response({'id': portfolio_id}, message='Portfolio created successfully', status_code=201)


@portfolio_bp.route('/list', methods=['GET'])
def list_portfolios():
    try:
        portfolios = PortfolioService.list_portfolios()
        result = []
        for portfolio in portfolios:
            value_data = PortfolioService.get_portfolio_value(portfolio['id'])
            portfolio.update(value_data)
            result.append(portfolio)
        return success_response({'portfolios': result})
    except Exception as e:
        return error_response(str(e), status_code=500, code='internal_server_error')


@portfolio_bp.route('/value/<int:portfolio_id>', methods=['GET'])
def get_value(portfolio_id):
    try:
        value_data = PortfolioService.get_portfolio_value(portfolio_id)
        if value_data:
            return success_response(value_data)
        return error_response('Portfolio not found', status_code=404, code='not_found')
    except Exception as e:
        return error_response(str(e), status_code=500, code='internal_server_error')


@portfolio_bp.route('/holdings/<int:portfolio_id>', methods=['GET'])
def get_holdings(portfolio_id):
    try:
        force_refresh = request.args.get('refresh') == '1'
        holdings = PortfolioService.get_holdings(portfolio_id, force_price_refresh=force_refresh)
        return success_response({'holdings': holdings})
    except Exception as e:
        return error_response(str(e), status_code=500, code='internal_server_error')


@portfolio_bp.route('/<int:portfolio_id>/clear', methods=['POST'])
def clear_portfolio(portfolio_id):
    try:
        result = PortfolioService.clear_portfolio_data(portfolio_id)
        return success_response(result, message='Portfolio data cleared successfully')
    except ValueError as e:
        message = str(e)
        if message == 'Portfolio not found':
            return error_response(message, status_code=404, code='not_found')
        return error_response(message, status_code=400, code='business_rule_error')
    except Exception as e:
        return error_response(str(e), status_code=500, code='internal_server_error')


@portfolio_bp.route('/<int:portfolio_id>', methods=['DELETE'])
def delete_portfolio(portfolio_id):
    try:
        PortfolioService.delete_portfolio(portfolio_id)
        return success_response(None, message='Portfolio deleted successfully')
    except ValueError as e:
        message = str(e)
        if message == 'Portfolio not found':
            return error_response(message, status_code=404, code='not_found')
        return error_response(message, status_code=400, code='business_rule_error')
    except Exception as e:
        return error_response(str(e), status_code=500, code='internal_server_error')


@portfolio_bp.route('/bonds/<int:portfolio_id>', methods=['GET'])
def get_bonds(portfolio_id):
    try:
        bonds = BondService.get_bonds(portfolio_id)
        return success_response({'bonds': bonds})
    except Exception as e:
        return error_response(str(e), status_code=500, code='internal_server_error')


@portfolio_bp.route('/bonds', methods=['POST'])
def add_bond():
    data = request.json
    try:
        BondService.add_bond(
            data['portfolio_id'],
            data['name'],
            data['principal'],
            data['interest_rate'],
            data['purchase_date']
        )
        return success_response(None, message='Bond added successfully', status_code=201)
    except Exception as e:
        return error_response(str(e), status_code=400, code='validation_error')


@portfolio_bp.route('/savings/rate', methods=['POST'])
def update_savings_rate():
    data = request.json
    try:
        PortfolioService.update_savings_rate(data['portfolio_id'], data['rate'])
        return success_response(None, message='Rate updated successfully')
    except Exception as e:
        return error_response(str(e), status_code=400, code='validation_error')


@portfolio_bp.route('/savings/interest/manual', methods=['POST'])
def add_manual_interest():
    data = request.json
    try:
        PortfolioService.add_manual_interest(data['portfolio_id'], data['amount'], data['date'])
        return success_response(None, message='Interest added successfully')
    except Exception as e:
        return error_response(str(e), status_code=400, code='validation_error')
