from flask import jsonify, request

from bond_service import BondService
from portfolio_service import PortfolioService
from routes_portfolio_base import portfolio_bp
from validators.request_models import validate_portfolio_create


@portfolio_bp.route('/limits', methods=['GET'])
def get_tax_limits():
    try:
        limits = PortfolioService.get_tax_limits()
        return jsonify({'limits': limits}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@portfolio_bp.route('/create', methods=['POST'])
def create_portfolio():
    data = validate_portfolio_create(request.get_json(silent=True))
    portfolio_id = PortfolioService.create_portfolio(
        data['name'],
        data['initial_cash'],
        data['account_type'],
        data.get('created_at')
    )
    return jsonify({'id': portfolio_id, 'message': 'Portfolio created successfully'}), 201


@portfolio_bp.route('/list', methods=['GET'])
def list_portfolios():
    try:
        portfolios = PortfolioService.list_portfolios()
        result = []
        for portfolio in portfolios:
            value_data = PortfolioService.get_portfolio_value(portfolio['id'])
            portfolio.update(value_data)
            result.append(portfolio)
        return jsonify({'portfolios': result}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@portfolio_bp.route('/value/<int:portfolio_id>', methods=['GET'])
def get_value(portfolio_id):
    try:
        value_data = PortfolioService.get_portfolio_value(portfolio_id)
        if value_data:
            return jsonify(value_data), 200
        return jsonify({'error': 'Portfolio not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@portfolio_bp.route('/holdings/<int:portfolio_id>', methods=['GET'])
def get_holdings(portfolio_id):
    try:
        force_refresh = request.args.get('refresh') == '1'
        holdings = PortfolioService.get_holdings(portfolio_id, force_price_refresh=force_refresh)
        return jsonify({'holdings': holdings}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@portfolio_bp.route('/<int:portfolio_id>/clear', methods=['POST'])
def clear_portfolio(portfolio_id):
    try:
        result = PortfolioService.clear_portfolio_data(portfolio_id)
        return jsonify({'message': 'Portfolio data cleared successfully', **result}), 200
    except ValueError as e:
        message = str(e)
        if message == 'Portfolio not found':
            return jsonify({'error': message}), 404
        return jsonify({'error': message}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@portfolio_bp.route('/<int:portfolio_id>', methods=['DELETE'])
def delete_portfolio(portfolio_id):
    try:
        PortfolioService.delete_portfolio(portfolio_id)
        return jsonify({'message': 'Portfolio deleted successfully'}), 200
    except ValueError as e:
        message = str(e)
        if message == 'Portfolio not found':
            return jsonify({'error': message}), 404
        return jsonify({'error': message}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@portfolio_bp.route('/bonds/<int:portfolio_id>', methods=['GET'])
def get_bonds(portfolio_id):
    try:
        bonds = BondService.get_bonds(portfolio_id)
        return jsonify({'bonds': bonds}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
        return jsonify({'message': 'Bond added successfully'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@portfolio_bp.route('/savings/rate', methods=['POST'])
def update_savings_rate():
    data = request.json
    try:
        PortfolioService.update_savings_rate(data['portfolio_id'], data['rate'])
        return jsonify({'message': 'Rate updated successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@portfolio_bp.route('/savings/interest/manual', methods=['POST'])
def add_manual_interest():
    data = request.json
    try:
        PortfolioService.add_manual_interest(data['portfolio_id'], data['amount'], data['date'])
        return jsonify({'message': 'Interest added successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400
