from flask import Flask
import logging
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from database import init_db
from api.exceptions import ApiError, NotFoundError, ValidationError
from api.response import error_response, success_response
from routes import portfolio_bp
from routes_loans import loans_bp
from routes_budget import budget_bp
from routes_dashboard import dashboard_bp
from routes_radar import radar_bp
from routes_symbol_map import symbol_map_bp
from price_service import PriceService
import os

def create_app():
    app = Flask(__name__)
    CORS(app)  # Enable CORS for all routes

    # Configure simple logging
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
    )

    # Database configuration
    db_path = os.path.join(os.path.dirname(__file__), 'portfolio.db')
    app.config['DATABASE'] = db_path

    # Initialize database
    init_db(app)

    # Warmup price cache
    with app.app_context():
        try:
            PriceService.warmup_cache()
        except Exception as e:
            logging.warning("Startup warmup failed (DB might not be ready): %s", e)

    # Register blueprints
    app.register_blueprint(portfolio_bp, url_prefix='/api/portfolio')
    app.register_blueprint(loans_bp, url_prefix='/api/loans')
    app.register_blueprint(budget_bp, url_prefix='/api/budget')
    app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
    app.register_blueprint(radar_bp, url_prefix='/api/radar')
    app.register_blueprint(symbol_map_bp, url_prefix='/api/symbol-map')


    # Global API error handling.
    #
    # Contract: unhandled exceptions are normalized to the canonical JSON error
    # envelope so new consumers can rely on a consistent structure.
    # Migration strategy: route-level legacy return shapes remain untouched for now;
    # only framework-level exception handling is standardized in this change.

    @app.errorhandler(ApiError)
    def handle_api_error(error):
        return error_response(
            getattr(error, 'code', 'api_error'),
            getattr(error, 'message', 'Request failed.'),
            details=getattr(error, 'details', None),
            status=getattr(error, 'status', 400),
        )

    @app.errorhandler(ValidationError)
    def handle_validation_error(error):
        return error_response(
            'validation_error',
            getattr(error, 'message', 'Validation failed.'),
            details=getattr(error, 'details', None),
            status=400,
        )

    @app.errorhandler(ValueError)
    def handle_value_error(error):
        return error_response(
            'value_error',
            str(error),
            status=400,
        )

    @app.errorhandler(NotFoundError)
    def handle_not_found_error(error):
        return error_response(
            'not_found',
            getattr(error, 'message', 'Resource not found.'),
            details=getattr(error, 'details', None),
            status=404,
        )

    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        return error_response(
            f'http_{error.code}',
            error.description,
            status=error.code,
        )

    @app.errorhandler(Exception)
    def handle_exception(error):
        logging.exception('Unhandled exception')
        # Never leak raw exception text for 500 responses; keep details in logs only.
        return error_response(
            'internal_error',
            'Internal server error',
            status=500,
        )

    @app.route('/')
    def health_check():
        return success_response({'status': 'healthy', 'message': 'Portfolio Manager API is running'})

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', debug=True, port=5000)
