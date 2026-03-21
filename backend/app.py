from flask import Flask
import logging
import traceback
from flask_cors import CORS
from database import init_db
from routes import portfolio_bp
from routes_loans import loans_bp
from routes_budget import budget_bp
from routes_dashboard import dashboard_bp
from routes_radar import radar_bp
from routes_symbol_map import symbol_map_bp
from price_service import PriceService
from validators.errors import BusinessRuleError, ValidationError
from validators.responses import error_response, success_response, validation_error_response
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

    @app.errorhandler(ValidationError)
    def handle_validation_error(error):
        return validation_error_response(error.message, error.errors, status_code=400)

    @app.errorhandler(ValueError)
    def handle_value_error(error):
        return error_response(str(error), status_code=400, code='business_rule_error')

    @app.errorhandler(BusinessRuleError)
    def handle_business_rule_error(error):
        return error_response(
            error.message,
            status_code=error.status_code,
            code=error.code,
        )

    # Global error handler to return consistent JSON responses
    @app.errorhandler(Exception)
    def handle_exception(e):
        logging.exception("Unhandled exception")
        if app.debug:
            traceback.print_exc()
            return error_response(str(e), status_code=500, code='internal_server_error')
        # don't expose internals in production responses
        return error_response('Internal server error', status_code=500, code='internal_server_error')

    @app.route('/')
    def health_check():
        return success_response(
            payload={'service': 'Portfolio Manager API'},
            message='Service is healthy',
        )

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', debug=True, port=5000)
