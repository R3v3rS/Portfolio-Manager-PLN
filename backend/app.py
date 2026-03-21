from flask import Flask
import logging
import traceback
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from database import init_db
from api_response import error_response
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


    # Global error handler to return consistent JSON responses

    @app.errorhandler(Exception)
    def handle_exception(e):
        if isinstance(e, HTTPException):
            return error_response(e.description, status_code=e.code)

        logging.exception("Unhandled exception")
        if app.debug:
            traceback.print_exc()
            return error_response(str(e), status_code=500, code='internal_error')
        # don't expose internals in production responses
        return error_response('Internal server error', status_code=500, code='internal_error')

    @app.route('/')
    def health_check():
        return {'status': 'healthy', 'message': 'Portfolio Manager API is running'}

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', debug=True, port=5000)
