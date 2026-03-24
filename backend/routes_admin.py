from flask import abort

from api.response import success_response
from portfolio_service import PortfolioService
from price_service import PriceService
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


@portfolio_bp.route('/admin/price-history-audit', methods=['GET'])
def audit_price_history():
    if not is_admin_debug_request():
        abort(403, description='Admin access required')

    from flask import request

    days = request.args.get('days', default=30, type=int)
    threshold = request.args.get('threshold', default=25.0, type=float)
    refresh_flagged = request.args.get('refresh_flagged', default='0') == '1'

    result = PriceService.audit_price_history_quality(
        days=days,
        jump_threshold_percent=threshold,
        refresh_flagged=refresh_flagged,
    )
    return success_response(result)
