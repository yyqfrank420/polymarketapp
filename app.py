"""Main Flask application - Clean microservices architecture"""
from flask import Flask, jsonify, render_template, request
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from config import Config
from utils.database import init_db, close_db

# Try to import CORS (optional)
try:
    from flask_cors import CORS
    CORS_AVAILABLE = True
except ImportError:
    CORS_AVAILABLE = False

# Try to import Flask-Limiter (optional)
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    LIMITER_AVAILABLE = True
except ImportError:
    LIMITER_AVAILABLE = False

# Initialize Flask app
app = Flask(__name__)

# Configure Flask
app.config['ENV'] = Config.FLASK_ENV
app.config['DEBUG'] = Config.DEBUG
app.config['SECRET_KEY'] = Config.SECRET_KEY or 'dev-secret-key-change-in-production'
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# CORS for cross-origin requests (optional)
if CORS_AVAILABLE:
    CORS(app)

# Rate limiting for API protection (optional)
limiter = None
if LIMITER_AVAILABLE:
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["100 per hour"],  # Global rate limit
        storage_uri="memory://"  # In-memory storage (use Redis in production)
    )
    logger = logging.getLogger(__name__)
    logger.info("Rate limiting enabled")
else:
    logger = logging.getLogger(__name__)
    logger.warning("Flask-Limiter not available - rate limiting disabled")

# Configure logging
if not app.debug:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
else:
    logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)

# Register blueprints
from routes.pages import pages_bp
from routes.api import api_bp
from routes.admin import admin_bp

app.register_blueprint(pages_bp)
app.register_blueprint(api_bp)
app.register_blueprint(admin_bp)

# Initialize services on startup
with app.app_context():
    try:
        # Validate configuration
        if app.config['ENV'] == 'production':
            Config.validate()
        
        # Initialize database
        init_db()
        
        # Initialize services (they initialize themselves)
        from services.blockchain_service import get_blockchain_service
        from services.chatbot_service import get_chatbot_service
        
        blockchain_service = get_blockchain_service()
        chatbot_service = get_chatbot_service()
        
        logger.info("Services initialized successfully")
        
    except Exception as e:
        logger.error(f"Initialization error: {e}")
        if app.config['ENV'] == 'production':
            raise

# Cleanup on request end
@app.teardown_appcontext
def close_database(error):
    """Close database connection"""
    close_db()

# Error handlers
@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors"""
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Endpoint not found'}), 404
    return render_template('index.html')

@app.errorhandler(500)
def internal_error(e):
    """Handle 500 errors"""
    logger.error(f'Internal server error: {str(e)}')
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error'}), 500
    return 'Internal server error. Please try again later.', 500

# Health check endpoint
@app.route('/health')
def health_check():
    """Health check endpoint"""
    try:
        from utils.database import get_db
        conn = get_db()
        conn.close()
        return jsonify({'status': 'healthy', 'database': 'connected'}), 200
    except Exception as e:
        logger.error(f'Health check failed: {str(e)}')
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 503

# Initialize database on import
try:
    init_db()
except Exception as e:
    logger.warning(f"Database initialization warning: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=Config.DEBUG)

