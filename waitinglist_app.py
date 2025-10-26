from flask import Flask, render_template, request, jsonify
import sqlite3
import os
import logging
from datetime import datetime
import stripe

app = Flask(__name__)

# Configure logging for production
if not app.debug:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
else:
    logger = logging.getLogger(__name__)

# Configuration
app.config['ENV'] = os.environ.get('FLASK_ENV', 'development')
app.config['DEBUG'] = app.config['ENV'] == 'development'
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Stripe Configuration
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', 'sk_test_51SMPehGf9P1kk0BnS9ypd2cPraRWqPfQtJHhPTcpcpuQHIkBxVjcRy1ubNJvkwCBkeYEZ5m9Es5gMWUZfxXonObj00ggxVBZmU')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', 'pk_test_51SMPehGf9P1kk0Bn6fixDPguXM8bSxEJy6F7wTmzQB7mVQtzEkFBpqg9xenscQDVArnvwfgBBUEn4IRVKNEUEBgj000B6a9RPe')
PRODUCT_ID = os.environ.get('STRIPE_PRODUCT_ID', 'prod_TJ1v4b9S6EUxIQ')

# Stripe is now properly configured

# Database setup - use absolute path for production
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, 'waitinglist.db')

def init_db():
    """Initialize the database if it doesn't exist"""
    if not os.path.exists(DATABASE):
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                latitude REAL,
                longitude REAL,
                ip_address TEXT,
                country TEXT,
                city TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    """Render the landing page"""
    return render_template('index.html', stripe_publishable_key=STRIPE_PUBLISHABLE_KEY)

@app.route('/api/register', methods=['POST'])
def register():
    """Handle email registration with geolocation"""
    try:
        data = request.get_json()
        if not data:
            logger.warning('Registration attempt with no JSON data')
            return jsonify({'success': False, 'message': 'Invalid request format'}), 400
        
        email = data.get('email', '').strip().lower()
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        country = data.get('country', '')
        city = data.get('city', '')
        ip_address = request.remote_addr
        
        # Validate email
        if not email or '@' not in email or len(email) < 5:
            logger.warning(f'Invalid email format attempted: {email}')
            return jsonify({'success': False, 'message': 'Please provide a valid email address'}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO registrations (email, latitude, longitude, ip_address, country, city)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (email, latitude, longitude, ip_address, country, city))
            conn.commit()
            
            # Get updated count
            cursor.execute('SELECT COUNT(*) as count FROM registrations')
            count = cursor.fetchone()['count']
            
            conn.close()
            
            logger.info(f'New registration: {email} from {country}')
            return jsonify({'success': True, 'message': 'Successfully registered!', 'count': count}), 200
            
        except sqlite3.IntegrityError:
            conn.close()
            logger.info(f'Duplicate registration attempt: {email}')
            return jsonify({'success': False, 'message': 'This email is already registered'}), 400
            
    except Exception as e:
        logger.error(f'Registration error: {str(e)}')
        return jsonify({'success': False, 'message': 'An error occurred. Please try again.'}), 500

@app.route('/api/count', methods=['GET'])
def get_count():
    """Get total number of registrations"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as count FROM registrations')
        count = cursor.fetchone()['count']
        conn.close()
        return jsonify({'count': count}), 200
    except Exception as e:
        logger.error(f'Count retrieval error: {str(e)}')
        return jsonify({'count': 0}), 200

# Stripe Routes
@app.route('/api/create-checkout-session', methods=['POST'])
def create_checkout_session():
    """Create a Stripe checkout session for premium subscription"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid request format'}), 400
        
        logger.info(f"Creating checkout session with Stripe API key: {stripe.api_key[:20]}...")
        logger.info(f"Product ID: {PRODUCT_ID}")
        
        # Create checkout session using your actual product
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'eur',
                    'product': PRODUCT_ID,  # Use your actual product ID
                    'unit_amount': 6767,  # €67.67 in cents
                    'recurring': {
                        'interval': 'month'
                    }
                },
                'quantity': 1,
            }],
            mode='subscription',  # Changed to subscription mode
            success_url=request.url_root + 'success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.url_root + 'cancel',
            metadata={
                'user_email': data.get('email', ''),
            }
        )
        
        logger.info(f"Checkout session created successfully: {checkout_session.id}")
        return jsonify({'checkout_url': checkout_session.url}), 200
        
    except stripe.error.StripeError as e:
        logger.error(f'Stripe API error: {str(e)}')
        return jsonify({'error': f'Stripe error: {str(e)}'}), 500
    except Exception as e:
        logger.error(f'General checkout error: {str(e)}')
        return jsonify({'error': 'Failed to create checkout session'}), 500

@app.route('/success')
def success():
    """Handle successful payment"""
    session_id = request.args.get('session_id')
    if session_id:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            logger.info(f'Payment successful for session: {session_id}')
            return render_template('success.html', session=session)
        except Exception as e:
            logger.error(f'Error retrieving session: {str(e)}')
    
    return render_template('success.html')

@app.route('/cancel')
def cancel():
    """Handle cancelled payment"""
    return render_template('cancel.html')

# Error handlers for production
@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors"""
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Endpoint not found'}), 404
    return render_template('index.html')  # Redirect to home for non-API 404s

@app.errorhandler(500)
def internal_error(e):
    """Handle 500 errors"""
    logger.error(f'Internal server error: {str(e)}')
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error'}), 500
    return 'Internal server error. Please try again later.', 500

# Health check endpoint for monitoring
@app.route('/health')
def health_check():
    """Simple health check endpoint"""
    try:
        # Test database connection
        conn = get_db()
        conn.close()
        return jsonify({'status': 'healthy', 'database': 'connected'}), 200
    except Exception as e:
        logger.error(f'Health check failed: {str(e)}')
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 503

# Initialize database on startup
init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)

