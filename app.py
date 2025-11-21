from flask import Flask, render_template, request, jsonify, redirect, url_for
import sqlite3
import os
import logging
from datetime import datetime
import stripe
from collections import defaultdict
import queue
import threading
import uuid
import math

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

# Stripe Configuration (hardcoded for test keys)
stripe.api_key = 'sk_test_51SMPehGf9P1kk0BnS9ypd2cPraRWqPfQtJHhPTcpcpuQHIkBxVjcRy1ubNJvkwCBkeYEZ5m9Es5gMWUZfxXonObj00ggxVBZmU'
STRIPE_PUBLISHABLE_KEY = 'pk_test_51SMPehGf9P1kk0Bn6fixDPguXM8bSxEJy6F7wTmzQB7mVQtzEkFBpqg9xenscQDVArnvwfgBBUEn4IRVKNEUEBgj000B6a9RPe'
PRODUCT_ID = 'prod_TJ1v4b9S6EUxIQ'

# Database setup - use absolute path for production
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, 'polymarket.db')

def init_db():
    """Initialize the database and required tables if they don't exist"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    # registrations (existing)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS registrations (
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
    # markets for prediction markets MVP
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS markets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            description TEXT,
            image_url TEXT,
            category TEXT,
            end_date TEXT,
            created_by TEXT,
            status TEXT DEFAULT 'open',
            resolution TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # bets table to record YES/NO orders
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_id INTEGER NOT NULL,
            wallet TEXT NOT NULL,
            side TEXT NOT NULL CHECK(side IN ('YES','NO')),
            amount REAL NOT NULL,
            shares REAL NOT NULL,
            price_per_share REAL NOT NULL,
            tx_hash TEXT,
            signature TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(market_id) REFERENCES markets(id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_bets_market ON bets(market_id)')
    # users table for fake crypto balance
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            wallet TEXT PRIMARY KEY,
            balance REAL DEFAULT 0.0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login DATETIME
        )
    ''')
    # market_state table for LMSR (tracks q_yes and q_no for each market)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS market_state (
            market_id INTEGER PRIMARY KEY,
            q_yes REAL DEFAULT 0.0,
            q_no REAL DEFAULT 0.0,
            FOREIGN KEY(market_id) REFERENCES markets(id)
        )
    ''')
    conn.commit()
    conn.close()

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# ========== USER BALANCE MANAGEMENT ==========
INITIAL_FAKE_CRYPTO_BALANCE = 1000.0  # Initial fake crypto credit (e.g., 1000 MATIC/USDC)

def get_user_balance(wallet):
    """Get user balance, create user if doesn't exist"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE wallet=?', (wallet,))
    row = cursor.fetchone()
    
    if not row:
        # First time user - credit them with fake crypto
        cursor.execute('''
            INSERT INTO users (wallet, balance, last_login)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (wallet, INITIAL_FAKE_CRYPTO_BALANCE))
        conn.commit()
        conn.close()
        logger.info(f'New user {wallet} credited with {INITIAL_FAKE_CRYPTO_BALANCE} fake crypto')
        return INITIAL_FAKE_CRYPTO_BALANCE
    
    balance = row['balance'] or 0.0
    conn.close()
    return balance

def update_user_balance(wallet, amount, operation='deduct'):
    """Update user balance (deduct or add)"""
    conn = get_db()
    cursor = conn.cursor()
    
    current_balance = get_user_balance(wallet)
    
    if operation == 'deduct':
        new_balance = max(0, current_balance - amount)
    else:  # add
        new_balance = current_balance + amount
    
    cursor.execute('UPDATE users SET balance=?, last_login=CURRENT_TIMESTAMP WHERE wallet=?', 
                  (new_balance, wallet))
    conn.commit()
    conn.close()
    
    return new_balance

def check_user_exists(wallet):
    """Check if user exists in database"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT wallet FROM users WHERE wallet=?', (wallet,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

# ========== BET QUEUE SYSTEM ==========
bet_queue = queue.Queue()
bet_results = {}  # Store results by request_id
bet_lock = threading.Lock()

def bet_worker():
    """Background worker that processes bets sequentially"""
    while True:
        try:
            bet_request = bet_queue.get()
            if bet_request is None:  # Shutdown signal
                break
            
            request_id = bet_request['request_id']
            market_id = bet_request['market_id']
            wallet = bet_request['wallet']
            side = bet_request['side']
            amount = bet_request['amount']
            tx_hash = bet_request.get('tx_hash')
            signature = bet_request.get('signature')
            
            try:
                conn = get_db()
                cursor = conn.cursor()
                
                # Check market status
                cursor.execute('SELECT status FROM markets WHERE id=?', (market_id,))
                row = cursor.fetchone()
                if not row:
                    bet_results[request_id] = {
                        'success': False,
                        'message': 'Market not found'
                    }
                    conn.close()
                    bet_queue.task_done()
                    continue
                
                if row['status'] != 'open':
                    bet_results[request_id] = {
                        'success': False,
                        'message': 'Market is not open'
                    }
                    conn.close()
                    bet_queue.task_done()
                    continue
                
                # Check user balance
                user_balance = get_user_balance(wallet)
                if user_balance < amount:
                    bet_results[request_id] = {
                        'success': False,
                        'message': f'Insufficient balance. You have ${user_balance:.2f}, need ${amount:.2f}'
                    }
                    conn.close()
                    bet_queue.task_done()
                    continue
                
                # Calculate shares using LMSR
                shares, price_per_share = calculate_shares_lmsr(amount, side, market_id)
                
                if shares <= 0:
                    bet_results[request_id] = {
                        'success': False,
                        'message': 'Invalid bet amount or market state'
                    }
                    conn.close()
                    bet_queue.task_done()
                    continue
                
                # Insert bet
                cursor.execute('''
                    INSERT INTO bets (market_id, wallet, side, amount, shares, price_per_share, tx_hash, signature)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (market_id, wallet, side, amount, shares, price_per_share, tx_hash, signature))
                
                # Deduct balance
                new_balance = update_user_balance(wallet, amount, 'deduct')
                
                conn.commit()
                conn.close()
                
                logger.info(f'Bet placed: market {market_id}, {side} ${amount:.2f} ({shares:.2f} shares @ ${price_per_share:.4f}) by {wallet}. New balance: ${new_balance:.2f}')
                
                bet_results[request_id] = {
                    'success': True,
                    'shares': shares,
                    'price_per_share': price_per_share
                }
                
            except Exception as e:
                logger.error(f'Bet processing error: {str(e)}')
                bet_results[request_id] = {
                    'success': False,
                    'message': f'Failed to place bet: {str(e)}'
                }
            
            bet_queue.task_done()
            
        except Exception as e:
            logger.error(f'Bet worker error: {str(e)}')

# Start worker thread
bet_worker_thread = threading.Thread(target=bet_worker, daemon=True)
bet_worker_thread.start()

@app.route('/')
def index():
    """Render the main customer-facing page showing all markets"""
    return render_template('index.html')

@app.route('/waitlist')
def waitlist_page():
    """Render the waitlist signup page"""
    return render_template('waitlist.html', stripe_publishable_key=STRIPE_PUBLISHABLE_KEY)

@app.route('/market/<int:market_id>')
def market_detail_page(market_id):
    """Render individual market detail page"""
    return render_template('market_detail.html', market_id=market_id)

@app.route('/admin')
def admin_page():
    """Render the admin dashboard"""
    return render_template('admin.html')

@app.route('/admin/create-market')
def admin_create_market_page():
    """Render the admin market creation page"""
    return render_template('admin_create_market.html')

@app.route('/admin/resolve')
def admin_resolve_page():
    """Render the admin resolution page"""
    return render_template('admin_resolve.html')

@app.route('/my-bets')
def my_bets_page():
    """Render the user's bets page"""
    return render_template('my_bets.html')

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

# ---------------------
# Markets MVP Endpoints
# ---------------------

def _row_to_dict(row):
    return {k: row[k] for k in row.keys()}

@app.route('/api/markets', methods=['GET'])
def list_markets():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM markets ORDER BY created_at DESC')
        markets = [dict(_row_to_dict(r)) for r in cursor.fetchall()]
        # attach aggregates and prices using LMSR
        for m in markets:
            cursor.execute('''SELECT
                               SUM(CASE WHEN side="YES" THEN amount ELSE 0 END) as yes_total,
                               SUM(CASE WHEN side="NO" THEN amount ELSE 0 END) as no_total,
                               COUNT(*) as bet_count
                             FROM bets WHERE market_id=?''', (m['id'],))
            agg = cursor.fetchone()
            m['yes_total'] = agg['yes_total'] or 0.0
            m['no_total'] = agg['no_total'] or 0.0
            m['bet_count'] = agg['bet_count'] or 0
            
            # Calculate prices using LMSR
            yes_price, no_price = calculate_market_price(m['id'])
            m['yes_price'] = yes_price
            m['no_price'] = no_price
            m['yes_price_cents'] = round(yes_price * 100, 2)
            m['no_price_cents'] = round(no_price * 100, 2)
        conn.close()
        return jsonify({'markets': markets}), 200
    except Exception as e:
        logger.error(f'Markets list error: {str(e)}')
        return jsonify({'markets': []}), 200

@app.route('/api/markets', methods=['POST'])
def create_market():
    try:
        data = request.get_json() or {}
        question = (data.get('question') or '').strip()
        description = (data.get('description') or '').strip()
        image_url = (data.get('image_url') or '').strip()
        category = (data.get('category') or '').strip()
        end_date = (data.get('end_date') or '').strip()
        created_by = (data.get('created_by') or '').strip()
        
        if not question:
            return jsonify({'success': False, 'message': 'Question is required'}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO markets (question, description, image_url, category, end_date, created_by) 
            VALUES (?,?,?,?,?,?)
        ''', (question, description, image_url, category, end_date, created_by))
        market_id = cursor.lastrowid
        
        # Initialize market state for LMSR
        cursor.execute('INSERT INTO market_state (market_id, q_yes, q_no) VALUES (?, 0.0, 0.0)', (market_id,))
        
        conn.commit()
        conn.close()
        logger.info(f'Created market {market_id}: {question} by {created_by}')
        return jsonify({'success': True, 'market_id': market_id}), 201
    except Exception as e:
        logger.error(f'Create market error: {str(e)}')
        return jsonify({'success': False, 'message': 'Failed to create market'}), 500

@app.route('/api/markets/<int:market_id>', methods=['GET'])
def get_market(market_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM markets WHERE id=?', (market_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'error': 'Not found'}), 404
        market = dict(_row_to_dict(row))
        cursor.execute('SELECT side, amount FROM bets WHERE market_id=?', (market_id,))
        bets = [dict(_row_to_dict(r)) for r in cursor.fetchall()]
        cursor.execute('''SELECT
                           SUM(CASE WHEN side="YES" THEN amount ELSE 0 END) as yes_total,
                           SUM(CASE WHEN side="NO" THEN amount ELSE 0 END) as no_total,
                           COUNT(*) as bet_count
                         FROM bets WHERE market_id=?''', (market_id,))
        agg = cursor.fetchone()
        conn.close()
        market['yes_total'] = agg['yes_total'] or 0.0
        market['no_total'] = agg['no_total'] or 0.0
        market['bet_count'] = agg['bet_count'] or 0
        
        # Calculate prices using LMSR
        yes_price, no_price = calculate_market_price(market_id)
        market['yes_price'] = yes_price
        market['no_price'] = no_price
        market['yes_price_cents'] = round(yes_price * 100, 2)
        market['no_price_cents'] = round(no_price * 100, 2)
        
        return jsonify({'market': market, 'bets': bets}), 200
    except Exception as e:
        logger.error(f'Get market error: {str(e)}')
        return jsonify({'error': 'Failed to fetch market'}), 500

# ========== LMSR (Logarithmic Market Scoring Rule) Configuration ==========
import math

# Liquidity parameter (b) - controls how sensitive prices are to trading volume
# Higher b = less sensitive prices, more liquidity
# Lower b = more sensitive prices, less liquidity
LMSR_B = 100.0  # Standard liquidity parameter

def get_market_state(market_id):
    """Get or initialize market state for LMSR"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT q_yes, q_no FROM market_state WHERE market_id=?', (market_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return row['q_yes'] or 0.0, row['q_no'] or 0.0
    else:
        # Initialize market state if it doesn't exist
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO market_state (market_id, q_yes, q_no) VALUES (?, 0.0, 0.0)', (market_id,))
        conn.commit()
        conn.close()
        return 0.0, 0.0

def update_market_state(market_id, q_yes, q_no):
    """Update market state for LMSR"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO market_state (market_id, q_yes, q_no)
        VALUES (?, ?, ?)
        ON CONFLICT(market_id) DO UPDATE SET q_yes=?, q_no=?
    ''', (market_id, q_yes, q_no, q_yes, q_no))
    conn.commit()
    conn.close()

def calculate_market_price(market_id):
    """
    Calculate market prices using LMSR (Logarithmic Market Scoring Rule)
    
    LMSR Formula:
    - Price(YES) = exp(q_yes/b) / (exp(q_yes/b) + exp(q_no/b))
    - Price(NO) = exp(q_no/b) / (exp(q_yes/b) + exp(q_no/b))
    
    Where:
    - q_yes: quantity of YES shares outstanding
    - q_no: quantity of NO shares outstanding
    - b: liquidity parameter
    """
    q_yes, q_no = get_market_state(market_id)
    
    # Calculate prices using LMSR formula
    exp_yes = math.exp(q_yes / LMSR_B)
    exp_no = math.exp(q_no / LMSR_B)
    total = exp_yes + exp_no
    
    if total == 0:
        # Initial state: 50/50
        yes_price = 0.5
        no_price = 0.5
    else:
        yes_price = exp_yes / total
        no_price = exp_no / total
    
    # Clamp to prevent extreme prices
    min_price = 0.01
    max_price = 0.99
    yes_price = max(min_price, min(max_price, yes_price))
    no_price = max(min_price, min(max_price, no_price))
    
    # Normalize to ensure they sum to 1.00
    total_price = yes_price + no_price
    yes_price = yes_price / total_price
    no_price = no_price / total_price
    
    return yes_price, no_price

def calculate_shares_lmsr(amount, side, market_id):
    """
    Calculate shares using LMSR cost function
    
    LMSR Cost Function:
    C(q) = b * ln(exp(q_yes/b) + exp(q_no/b))
    
    To buy shares:
    1. Calculate current cost: C(q_current)
    2. Calculate new cost after purchase: C(q_new)
    3. Cost to user = C(q_new) - C(q_current)
    4. Shares received = amount / average_price
    
    For binary markets:
    - Buying YES: increases q_yes, cost = b * ln((exp(q_yes/b) + exp(q_no/b)) / (exp(q_yes_old/b) + exp(q_no/b)))
    - Buying NO: increases q_no, cost = b * ln((exp(q_yes/b) + exp(q_no/b)) / (exp(q_yes/b) + exp(q_no_old/b)))
    """
    q_yes, q_no = get_market_state(market_id)
    
    # Calculate current cost
    exp_yes = math.exp(q_yes / LMSR_B)
    exp_no = math.exp(q_no / LMSR_B)
    current_cost = LMSR_B * math.log(exp_yes + exp_no) if (exp_yes + exp_no) > 0 else 0
    
    # Calculate new state after purchase
    if side == 'YES':
        # Buying YES shares increases q_yes
        # We need to solve: cost = b * ln((exp((q_yes + delta)/b) + exp(q_no/b)) / (exp(q_yes/b) + exp(q_no/b)))
        # For simplicity, we'll use iterative approach or approximation
        
        # Approximate: buying amount worth of YES shares
        # Price per share ≈ current YES price
        current_yes_price, _ = calculate_market_price(market_id)
        
        # Shares received = amount / price
        shares = amount / current_yes_price if current_yes_price > 0 else 0
        
        # Update q_yes proportionally (simplified approach)
        # In full LMSR, we'd solve the cost function exactly
        new_q_yes = q_yes + shares
        
        # Update market state
        update_market_state(market_id, new_q_yes, q_no)
        
        # Calculate effective price per share
        price_per_share = current_yes_price
        
    else:  # NO
        # Buying NO shares increases q_no
        _, current_no_price = calculate_market_price(market_id)
        
        shares = amount / current_no_price if current_no_price > 0 else 0
        
        new_q_no = q_no + shares
        
        # Update market state
        update_market_state(market_id, q_yes, new_q_no)
        
        price_per_share = current_no_price
    
    # Ensure shares are positive
    shares = max(0, shares)
    
    return shares, price_per_share

@app.route('/api/markets/<int:market_id>/bet', methods=['POST'])
def place_bet(market_id):
    """Queue bet for processing and return immediately"""
    try:
        data = request.get_json() or {}
        wallet = (data.get('wallet') or '').strip()
        side = (data.get('side') or '').strip().upper()
        amount = float(data.get('amount') or 0)
        tx_hash = (data.get('tx_hash') or '').strip() or None
        signature = (data.get('signature') or '').strip() or None

        # Validation
        if side not in ('YES', 'NO'):
            return jsonify({'success': False, 'message': 'Side must be YES or NO'}), 400
        if amount <= 0:
            return jsonify({'success': False, 'message': 'Amount must be positive'}), 400
        if not wallet:
            return jsonify({'success': False, 'message': 'Wallet is required'}), 400

        # Quick market check (before queuing)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT status FROM markets WHERE id=?', (market_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return jsonify({'success': False, 'message': 'Market not found'}), 404
        if row['status'] != 'open':
            return jsonify({'success': False, 'message': 'Market is not open'}), 400

        # Generate unique request ID
        request_id = str(uuid.uuid4())
        
        # Add to queue
        bet_queue.put({
            'request_id': request_id,
            'market_id': market_id,
            'wallet': wallet,
            'side': side,
            'amount': amount,
            'tx_hash': tx_hash,
            'signature': signature
        })
        
        # Return immediately with queued status
        return jsonify({
            'success': True,
            'status': 'queued',
            'request_id': request_id,
            'message': 'Your bet is being processed...'
        }), 202  # 202 Accepted
        
    except Exception as e:
        logger.error(f'Place bet error: {str(e)}')
        return jsonify({'success': False, 'message': 'Failed to queue bet'}), 500

@app.route('/api/bets/<request_id>/status', methods=['GET'])
def check_bet_status(request_id):
    """Check if bet has been processed"""
    if request_id in bet_results:
        result = bet_results.pop(request_id)  # Remove after fetching
        return jsonify(result), 200
    else:
        return jsonify({
            'success': False,
            'status': 'processing',
            'message': 'Bet is still being processed...'
        }), 202

@app.route('/api/markets/<int:market_id>/resolve', methods=['POST'])
def resolve_market(market_id):
    try:
        data = request.get_json() or {}
        outcome = (data.get('outcome') or '').strip().upper()
        if outcome not in ('YES', 'NO'):
            return jsonify({'success': False, 'message': 'Outcome must be YES or NO'}), 400

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT status FROM markets WHERE id=?', (market_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'message': 'Market not found'}), 404
        if row['status'] == 'resolved':
            conn.close()
            return jsonify({'success': False, 'message': 'Market already resolved'}), 400
        cursor.execute('UPDATE markets SET status="resolved", resolution=? WHERE id=?', (outcome, market_id))
        conn.commit()
        conn.close()
        logger.info(f'Market {market_id} resolved as {outcome}')
        return jsonify({'success': True}), 200
    except Exception as e:
        logger.error(f'Resolve market error: {str(e)}')
        return jsonify({'success': False, 'message': 'Failed to resolve market'}), 500

@app.route('/api/markets/<int:market_id>/payouts', methods=['GET'])
def get_market_payouts(market_id):
    """Calculate payouts for all users in a resolved market (AMM style)"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get market info
        cursor.execute('SELECT status, resolution FROM markets WHERE id=?', (market_id,))
        market = cursor.fetchone()
        if not market:
            conn.close()
            return jsonify({'error': 'Market not found'}), 404
        
        if market['status'] != 'resolved':
            conn.close()
            return jsonify({'error': 'Market not resolved yet'}), 400
        
        winning_side = market['resolution']
        
        # Get all bets with shares info
        cursor.execute('SELECT wallet, side, amount, shares, price_per_share FROM bets WHERE market_id=?', (market_id,))
        bets = [dict(_row_to_dict(r)) for r in cursor.fetchall()]
        conn.close()
        
        # Calculate payouts for each wallet (AMM style: $1 per winning share)
        payouts = {}
        total_amount_bet = 0
        total_payout = 0
        
        for bet in bets:
            wallet = bet['wallet']
            if wallet not in payouts:
                payouts[wallet] = {
                    'wallet': wallet,
                    'total_bet': 0,
                    'total_shares': 0,
                    'payout': 0,
                    'profit': 0,
                    'bets': []
                }
            
            bet_amount = bet['amount']
            bet_shares = bet['shares'] or 0
            total_amount_bet += bet_amount
            
            payouts[wallet]['total_bet'] += bet_amount
            payouts[wallet]['total_shares'] += bet_shares
            
            if bet['side'] == winning_side:
                # Winner gets $1 per share
                bet_payout = bet_shares * 1.0  # $1 per winning share
                payouts[wallet]['payout'] += bet_payout
                total_payout += bet_payout
                
                payouts[wallet]['bets'].append({
                    'side': bet['side'],
                    'amount': bet_amount,
                    'shares': bet_shares,
                    'price_per_share': bet['price_per_share'] or 0,
                    'result': 'won',
                    'payout': bet_payout
                })
            else:
                # Loser gets nothing
                payouts[wallet]['bets'].append({
                    'side': bet['side'],
                    'amount': bet_amount,
                    'shares': bet_shares,
                    'price_per_share': bet['price_per_share'] or 0,
                    'result': 'lost',
                    'payout': 0
                })
        
        # Calculate profit for each wallet and credit payouts
        for wallet_data in payouts.values():
            wallet_data['profit'] = wallet_data['payout'] - wallet_data['total_bet']
            # Credit payout to user balance
            if wallet_data['payout'] > 0:
                update_user_balance(wallet_data['wallet'], wallet_data['payout'], 'add')
                logger.info(f'Credited {wallet_data["wallet"]} with ${wallet_data["payout"]:.2f} payout')
        
        return jsonify({
            'market_id': market_id,
            'resolution': winning_side,
            'total_amount_bet': total_amount_bet,
            'total_payout': total_payout,
            'payouts': list(payouts.values())
        }), 200
        
    except Exception as e:
        logger.error(f'Payouts calculation error: {str(e)}')
        return jsonify({'error': 'Failed to calculate payouts'}), 500

@app.route('/api/activity/recent', methods=['GET'])
def get_recent_activity():
    """Get recent betting activity with probability changes"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get recent bets (last 50 transactions)
        cursor.execute('''
            SELECT b.id, b.market_id, b.side, b.amount, b.shares, b.created_at, b.wallet,
                   m.question, m.status, m.image_url
            FROM bets b
            JOIN markets m ON b.market_id = m.id
            WHERE m.status = 'open'
            ORDER BY b.created_at DESC
            LIMIT 50
        ''')
        
        recent_bets = []
        
        for row in cursor.fetchall():
            bet = dict(_row_to_dict(row))
            market_id = bet['market_id']
            
            # Get current market totals
            cursor.execute('''
                SELECT 
                    SUM(CASE WHEN side="YES" THEN amount ELSE 0 END) as yes_total,
                    SUM(CASE WHEN side="NO" THEN amount ELSE 0 END) as no_total
                FROM bets 
                WHERE market_id=?
            ''', (market_id,))
            
            totals = cursor.fetchone()
            yes_total = totals['yes_total'] or 0.0
            no_total = totals['no_total'] or 0.0
            
            # Calculate current probability using LMSR
            current_yes_price, current_no_price = calculate_market_price(market_id)
            
            # For previous probability, we need to temporarily adjust market state
            # Get current state
            q_yes, q_no = get_market_state(market_id)
            
            # Calculate previous state (before this bet)
            if bet['side'] == 'YES':
                prev_q_yes = q_yes - bet['shares'] if bet.get('shares') else q_yes
                prev_q_no = q_no
            else:
                prev_q_yes = q_yes
                prev_q_no = q_no - bet['shares'] if bet.get('shares') else q_no
            
            # Calculate previous price (temporarily update state)
            temp_q_yes, temp_q_no = get_market_state(market_id)
            update_market_state(market_id, prev_q_yes, prev_q_no)
            prev_yes_price, prev_no_price = calculate_market_price(market_id)
            # Restore state
            update_market_state(market_id, temp_q_yes, temp_q_no)
            
            # Calculate change
            prob_change = (current_yes_price - prev_yes_price) * 100
            
            # Show ALL transactions (not filtered by market)
            recent_bets.append({
                'id': bet['id'],
                'market_id': market_id,
                'question': bet['question'],
                'image_url': bet['image_url'],
                'side': bet['side'],
                'amount': bet['amount'],
                'shares': bet['shares'],
                'wallet': bet['wallet'],
                'current_probability': round(current_yes_price * 100, 1),
                'probability_change': round(prob_change, 1),
                'created_at': bet['created_at']
            })
        
        conn.close()
        return jsonify({'activity': recent_bets}), 200
        
    except Exception as e:
        logger.error(f'Recent activity error: {str(e)}')
        return jsonify({'activity': []}), 200

@app.route('/api/markets/<int:market_id>/sell', methods=['POST'])
def sell_shares(market_id):
    """Sell shares back to the market at current price"""
    try:
        data = request.get_json() or {}
        wallet = (data.get('wallet') or '').strip()
        bet_id = int(data.get('bet_id') or 0)
        shares_to_sell = float(data.get('shares') or 0)

        if not wallet:
            return jsonify({'success': False, 'message': 'Wallet is required'}), 400
        if bet_id <= 0:
            return jsonify({'success': False, 'message': 'Bet ID is required'}), 400
        if shares_to_sell <= 0:
            return jsonify({'success': False, 'message': 'Shares amount must be positive'}), 400

        conn = get_db()
        cursor = conn.cursor()
        
        # Get the bet and verify ownership
        cursor.execute('''
            SELECT b.id, b.market_id, b.side, b.shares, b.amount, b.price_per_share,
                   m.status
            FROM bets b
            JOIN markets m ON b.market_id = m.id
            WHERE b.id = ? AND b.wallet = ? AND m.status = 'open'
        ''', (bet_id, wallet))
        
        bet_row = cursor.fetchone()
        if not bet_row:
            conn.close()
            return jsonify({'success': False, 'message': 'Bet not found or market is not open'}), 404
        
        bet = dict(_row_to_dict(bet_row))
        current_shares = bet['shares'] or 0
        
        if shares_to_sell > current_shares:
            conn.close()
            return jsonify({'success': False, 'message': f'Cannot sell more than {current_shares:.2f} shares'}), 400
        
        # Get current market prices
        cursor.execute('''
            SELECT 
                SUM(CASE WHEN side="YES" THEN amount ELSE 0 END) as yes_total,
                SUM(CASE WHEN side="NO" THEN amount ELSE 0 END) as no_total
            FROM bets 
            WHERE market_id=?
        ''', (market_id,))
        
        totals = cursor.fetchone()
        yes_total = totals['yes_total'] or 0.0
        no_total = totals['no_total'] or 0.0
        
        # Calculate current price using LMSR
        current_yes_price, current_no_price = calculate_market_price(market_id)
        current_price = current_yes_price if bet['side'] == 'YES' else current_no_price
        
        # Calculate sell value (shares * current price)
        sell_value = shares_to_sell * current_price
        
        # Update bet: reduce shares and amount proportionally
        remaining_shares = current_shares - shares_to_sell
        remaining_amount = bet['amount'] * (remaining_shares / current_shares) if current_shares > 0 else 0
        
        if remaining_shares < 0.01:
            # Sell all shares - delete the bet
            cursor.execute('DELETE FROM bets WHERE id=?', (bet_id,))
        else:
            # Update shares and amount
            cursor.execute('''
                UPDATE bets 
                SET shares = ?, amount = ?
                WHERE id = ?
            ''', (remaining_shares, remaining_amount, bet_id))
        
        # Credit balance from selling shares
        update_user_balance(wallet, sell_value, 'add')
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Sold {shares_to_sell:.2f} shares for ${sell_value:.2f}',
            'shares_sold': round(shares_to_sell, 2),
            'sell_value': round(sell_value, 2),
            'remaining_shares': round(remaining_shares, 2) if remaining_shares >= 0.01 else 0,
            'current_price': round(current_price, 4)
        }), 200
        
    except Exception as e:
        logger.error(f'Sell shares error: {str(e)}')
        return jsonify({'success': False, 'message': f'Failed to sell shares: {str(e)}'}), 500

@app.route('/api/user/<wallet>/bets', methods=['GET'])
def get_user_bets(wallet):
    """Get all bets for a specific wallet with payout information (AMM style)"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get all bets for this wallet
        cursor.execute('''
            SELECT b.id, b.market_id, b.side, b.amount, b.shares, b.price_per_share, b.created_at,
                   m.question, m.status, m.resolution, m.description, m.image_url
            FROM bets b
            JOIN markets m ON b.market_id = m.id
            WHERE b.wallet = ?
            ORDER BY b.created_at DESC
        ''', (wallet,))
        
        bets = []
        for row in cursor.fetchall():
            bet_info = dict(_row_to_dict(row))
            
            # Calculate payout if market is resolved (AMM style)
            if bet_info['status'] == 'resolved':
                resolution = bet_info['resolution']
                shares = bet_info['shares'] or 0
                
                if bet_info['side'] == resolution:
                    # Winner: gets $1 per share
                    payout = shares * 1.0
                    bet_info['result'] = 'won'
                    bet_info['payout'] = round(payout, 2)
                    bet_info['profit'] = round(payout - bet_info['amount'], 2)
                else:
                    # Loser: gets nothing
                    bet_info['result'] = 'lost'
                    bet_info['payout'] = 0
                    bet_info['profit'] = -bet_info['amount']
            else:
                # Calculate unrealized profit/loss for open markets
                bet_info['result'] = 'pending'
                bet_info['payout'] = None
                bet_info['profit'] = None
                
                # Get current market prices
                cursor.execute('''
                    SELECT 
                        SUM(CASE WHEN side="YES" THEN amount ELSE 0 END) as yes_total,
                        SUM(CASE WHEN side="NO" THEN amount ELSE 0 END) as no_total
                    FROM bets 
                    WHERE market_id=?
                ''', (bet_info['market_id'],))
                
                totals = cursor.fetchone()
                yes_total = totals['yes_total'] or 0.0
                no_total = totals['no_total'] or 0.0
                
                # Calculate current price using LMSR
                current_yes_price, current_no_price = calculate_market_price(bet_info['market_id'])
                current_price = current_yes_price if bet_info['side'] == 'YES' else current_no_price
                
                # Calculate current value and unrealized profit
                shares = bet_info['shares'] or 0
                current_value = shares * current_price
                unrealized_profit = current_value - bet_info['amount']
                
                bet_info['current_price'] = round(current_price, 4)
                bet_info['current_value'] = round(current_value, 2)
                bet_info['unrealized_profit'] = round(unrealized_profit, 2)
                bet_info['buy_price'] = bet_info['price_per_share']
            
            bets.append(bet_info)
        
        conn.close()
        return jsonify({'bets': bets}), 200
        
    except Exception as e:
        logger.error(f'Get user bets error: {str(e)}')
        return jsonify({'bets': []}), 200

@app.route('/api/markets/<int:market_id>/price', methods=['GET'])
def get_market_price(market_id):
    """Get current prices for YES and NO shares"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Calculate prices using LMSR
        yes_price, no_price = calculate_market_price(market_id)
        conn.close()
        
        return jsonify({
            'yes_price': round(yes_price, 4),
            'no_price': round(no_price, 4),
            'yes_price_cents': round(yes_price * 100, 2),
            'no_price_cents': round(no_price * 100, 2)
        }), 200
        
    except Exception as e:
        logger.error(f'Get market price error: {str(e)}')
        return jsonify({'error': 'Failed to get prices'}), 500

# ========== USER BALANCE API ENDPOINTS ==========
@app.route('/api/user/<wallet>/balance', methods=['GET'])
def get_user_balance_api(wallet):
    """Get user balance, auto-credit on first login"""
    try:
        balance = get_user_balance(wallet)
        is_new_user = balance == INITIAL_FAKE_CRYPTO_BALANCE
        
        return jsonify({
            'wallet': wallet,
            'balance': round(balance, 2),
            'is_new_user': is_new_user
        }), 200
    except Exception as e:
        logger.error(f'Get balance error: {str(e)}')
        return jsonify({'error': 'Failed to get balance'}), 500

@app.route('/api/user/<wallet>/credit', methods=['POST'])
def credit_user(wallet):
    """Manually credit user (for admin/testing)"""
    try:
        data = request.get_json() or {}
        amount = float(data.get('amount', INITIAL_FAKE_CRYPTO_BALANCE))
        
        # Ensure user exists
        get_user_balance(wallet)
        
        # Credit balance
        new_balance = update_user_balance(wallet, amount, 'add')
        
        logger.info(f'Credited {wallet} with ${amount:.2f}. New balance: ${new_balance:.2f}')
        
        return jsonify({
            'success': True,
            'wallet': wallet,
            'credited': round(amount, 2),
            'new_balance': round(new_balance, 2)
        }), 200
    except Exception as e:
        logger.error(f'Credit user error: {str(e)}')
        return jsonify({'error': 'Failed to credit user'}), 500

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
