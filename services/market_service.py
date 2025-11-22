"""Market and LMSR pricing service"""
import math
import threading
from utils.database import get_db, db_transaction
from config import Config

# Thread-safe market state operations
_market_state_lock = threading.Lock()

def get_market_state(market_id):
    """Get or initialize market state for LMSR (single transaction)"""
    with _market_state_lock:
        with db_transaction() as conn:
            cursor = conn.cursor()
            
            # Check if market exists first
            cursor.execute('SELECT id FROM markets WHERE id=?', (market_id,))
            if not cursor.fetchone():
                raise ValueError(f"Market {market_id} does not exist")
            
            # Get market state
            cursor.execute('SELECT q_yes, q_no FROM market_state WHERE market_id=?', (market_id,))
            row = cursor.fetchone()
            
            if row:
                return row['q_yes'] or Config.LMSR_BUFFER, row['q_no'] or Config.LMSR_BUFFER
            else:
                # Initialize market state with $10k buffer on each side (prevents early swings)
                # This means market starts at 50/50 even after small bets
                buffer = Config.LMSR_BUFFER
                cursor.execute('INSERT INTO market_state (market_id, q_yes, q_no) VALUES (?, ?, ?)', 
                             (market_id, buffer, buffer))
                return buffer, buffer

def update_market_state(market_id, q_yes, q_no):
    """Update market state for LMSR"""
    with _market_state_lock:
        with db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO market_state (market_id, q_yes, q_no)
                VALUES (?, ?, ?)
                ON CONFLICT(market_id) DO UPDATE SET q_yes=?, q_no=?
            ''', (market_id, q_yes, q_no, q_yes, q_no))

def calculate_market_price(market_id):
    """
    Calculate market prices using LMSR (Logarithmic Market Scoring Rule)
    
    LMSR Formula:
    - Price(YES) = exp(q_yes/b) / (exp(q_yes/b) + exp(q_no/b))
    - Price(NO) = exp(q_no/b) / (exp(q_yes/b) + exp(q_no/b))
    """
    try:
        q_yes, q_no = get_market_state(market_id)
    except ValueError as e:
        raise ValueError(f"Cannot calculate price: {e}")
    
    # Calculate prices using LMSR formula with overflow protection
    # Price(Yes) = 1 / (1 + exp((q_no - q_yes) / b))
    try:
        exponent = (q_no - q_yes) / Config.LMSR_B
        # Clamp exponent to avoid overflow
        exponent = max(-700, min(700, exponent))
        yes_price = 1.0 / (1.0 + math.exp(exponent))
        no_price = 1.0 - yes_price
    except OverflowError:
        # Should not happen with clamping, but safety fallback
        yes_price = 0.99 if q_yes > q_no else 0.01
        no_price = 1.0 - yes_price
    
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
    """Calculate shares using LMSR cost function"""
    q_yes, q_no = get_market_state(market_id)
    
    if side == 'YES':
        current_yes_price, _ = calculate_market_price(market_id)
        shares = amount / current_yes_price if current_yes_price > 0 else 0
        new_q_yes = q_yes + shares
        update_market_state(market_id, new_q_yes, q_no)
        price_per_share = current_yes_price
    else:  # NO
        _, current_no_price = calculate_market_price(market_id)
        shares = amount / current_no_price if current_no_price > 0 else 0
        new_q_no = q_no + shares
        update_market_state(market_id, q_yes, new_q_no)
        price_per_share = current_no_price
    
    shares = max(0, shares)
    return shares, price_per_share

