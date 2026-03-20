from flask import jsonify

from portfolio_service import PortfolioService
from routes_portfolio_base import is_admin_debug_request, portfolio_bp


@portfolio_bp.route('/<int:portfolio_id>/audit', methods=['GET'])
def audit_portfolio(portfolio_id):
    try:
        result = PortfolioService.audit_portfolio_integrity(portfolio_id)
        return jsonify(result), 200
    except ValueError as e:
        message = str(e)
        status = 404 if message == 'Portfolio not found' else 400
        return jsonify({'error': message}), status
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@portfolio_bp.route('/<int:portfolio_id>/rebuild', methods=['POST'])
def rebuild_portfolio(portfolio_id):
    if not is_admin_debug_request():
        return jsonify({'error': 'Admin access required'}), 403

    try:
        result = PortfolioService.repair_portfolio_state(portfolio_id)
        return jsonify(result), 200
    except ValueError as e:
        message = str(e)
        status = 404 if message == 'Portfolio not found' else 400
        return jsonify({'error': message}), status
    except Exception as e:
        return jsonify({'error': str(e)}), 500
