from flask import abort

from api.response import success_response
from portfolio_service import PortfolioService
from routes_portfolio_base import (
    is_admin_debug_request,
    portfolio_bp,
    raise_portfolio_validation_error,
)


@portfolio_bp.route('/<int:portfolio_id>/audit', methods=['GET'])
def audit_portfolio(portfolio_id):
    try:
        result = PortfolioService.audit_portfolio_integrity(portfolio_id)
    except ValueError as error:
        raise_portfolio_validation_error(error)
    return success_response(result)


@portfolio_bp.route('/<int:portfolio_id>/rebuild', methods=['POST'])
def rebuild_portfolio(portfolio_id):
    if not is_admin_debug_request():
        abort(403, description='Admin access required')

    try:
        result = PortfolioService.repair_portfolio_state(portfolio_id)
    except ValueError as error:
        raise_portfolio_validation_error(error)
    return success_response(result)
