from flask import Flask
from flask_cors import CORS
from database import init_db
from routes import portfolio_bp
from services import PriceService
import os

def create_app():
    app = Flask(__name__)
    CORS(app)  # Enable CORS for all routes

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
            print(f"Startup warmup failed (DB might not be ready): {e}")

    # Register blueprints
    app.register_blueprint(portfolio_bp, url_prefix='/api/portfolio')

    @app.route('/')
    def health_check():
        return {'status': 'healthy', 'message': 'Portfolio Manager API is running'}

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
