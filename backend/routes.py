from routes_portfolio_base import portfolio_bp

# Import route modules so they attach endpoints to the shared portfolio blueprint.
import routes_admin  # noqa: F401
import routes_history  # noqa: F401
import routes_imports  # noqa: F401
import routes_portfolios  # noqa: F401
import routes_ppk  # noqa: F401
import routes_transactions  # noqa: F401

__all__ = ['portfolio_bp']
