from portfolio_service import PortfolioService
from routes_portfolio_base import is_admin_debug_request, portfolio_bp
from validators.responses import error_response, success_response


@portfolio_bp.route('/<int:portfolio_id>/audit', methods=['GET'])
def audit_portfolio(portfolio_id):
    try:
        result = PortfolioService.audit_portfolio_integrity(portfolio_id)
        return success_response(result)
    except ValueError as e:
        message = str(e)
        status = 404 if message == 'Portfolio not found' else 400
        code = 'not_found' if status == 404 else 'business_rule_error'
        return error_response(message, status_code=status, code=code)
    except Exception as e:
        return error_response(str(e), status_code=500, code='internal_server_error')


@portfolio_bp.route('/<int:portfolio_id>/rebuild', methods=['POST'])
def rebuild_portfolio(portfolio_id):
    if not is_admin_debug_request():
        return error_response('Admin access required', status_code=403, code='forbidden')

    try:
        result = PortfolioService.repair_portfolio_state(portfolio_id)
        return success_response(result)
    except ValueError as e:
        message = str(e)
        status = 404 if message == 'Portfolio not found' else 400
        code = 'not_found' if status == 404 else 'business_rule_error'
        return error_response(message, status_code=status, code=code)
    except Exception as e:
        return error_response(str(e), status_code=500, code='internal_server_error')
