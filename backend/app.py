from flask import Flask
import json
import logging
import os
import sys
from datetime import datetime, timezone

from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from api.exceptions import ApiError, NotFoundError, ValidationError
from api.response import error_response, success_response
from database import init_db
from price_service import PriceService
from monitoring import monitoring_bp
from routes import portfolio_bp
from routes_budget import budget_bp
from routes_dashboard import dashboard_bp
from routes_loans import loans_bp
from routes_radar import radar_bp
from routes_symbol_map import symbol_map_bp
from routes_analytics import analytics_bp


class JsonLineFormatter(logging.Formatter):
    """Emit one JSON object per line for file-based log shipping."""

    def format(self, record):
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
        }

        message = record.getMessage()
        parsed_message = None
        if isinstance(message, str):
            try:
                parsed_message = json.loads(message)
            except json.JSONDecodeError:
                parsed_message = None

        if isinstance(parsed_message, dict):
            payload.update(parsed_message)
        else:
            payload["message"] = message

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def configure_logging():
    logs_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    backend_log_path = os.path.join(logs_dir, "backend.log")

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )

    file_handler = logging.FileHandler(backend_log_path, encoding="utf-8")
    file_handler.setFormatter(JsonLineFormatter())

    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)

    logging.getLogger(__name__).info("Backend file logs enabled at %s", backend_log_path)
    return backend_log_path


def create_app():
    app = Flask(__name__)
    CORS(app)  # Enable CORS for all routes

    backend_log_path = configure_logging()
    app.config["BACKEND_LOG_PATH"] = backend_log_path
    app.config["APP_STARTED_AT"] = datetime.now(timezone.utc)

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
    app.register_blueprint(analytics_bp)
    app.register_blueprint(monitoring_bp, url_prefix='/monitoring')


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
