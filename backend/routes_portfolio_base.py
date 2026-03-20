from flask import Blueprint, current_app, request
import os

portfolio_bp = Blueprint('portfolio', __name__)


def is_admin_debug_request() -> bool:
    admin_token = os.getenv('PORTFOLIO_ADMIN_TOKEN')
    if admin_token:
        return request.headers.get('X-Admin-Token') == admin_token
    return bool(current_app.debug)
