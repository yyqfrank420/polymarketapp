"""Market and LMSR pricing service"""
import math
import threading
from utils.database import get_db, db_transaction
from utils.cache import get_cache
from config import Config

_cache = get_cache()

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
                # Always enforce minimum buffer - never allow values below buffer (handles old markets and prevents 0.0)
                q_yes = row['q_yes'] if (row['q_yes'] is not None and row['q_yes'] >= Config.LMSR_BUFFER) else Config.LMSR_BUFFER
                q_no = row['q_no'] if (row['q_no'] is not None and row['q_no'] >= Config.LMSR_BUFFER) else Config.LMSR_BUFFER
                
                # If we had to use buffer (values were None, 0, or below buffer), update the database to persist it
                if (row['q_yes'] is None or row['q_yes'] < Config.LMSR_BUFFER) or (row['q_no'] is None or row['q_no'] < Config.LMSR_BUFFER):
                    cursor.execute('''
                        UPDATE market_state SET q_yes=?, q_no=? WHERE market_id=?
                    ''', (q_yes, q_no, market_id))
                
                return q_yes, q_no
            else:
                # Initialize market state with $10k buffer on each side (prevents early swings)
                # This means market starts at 50/50 even after small bets
                buffer = Config.LMSR_BUFFER
                cursor.execute('INSERT INTO market_state (market_id, q_yes, q_no) VALUES (?, ?, ?)', 
                             (market_id, buffer, buffer))
                return buffer, buffer

def update_market_state(market_id, q_yes, q_no):
    """Update market state for LMSR - always enforces minimum buffer"""
    with _market_state_lock:
        with db_transaction() as conn:
            cursor = conn.cursor()
            # Always enforce minimum buffer - never allow 0.0 values
            q_yes = max(Config.LMSR_BUFFER, q_yes) if q_yes is not None else Config.LMSR_BUFFER
            q_no = max(Config.LMSR_BUFFER, q_no) if q_no is not None else Config.LMSR_BUFFER
            
            cursor.execute('''
                INSERT INTO market_state (market_id, q_yes, q_no)
                VALUES (?, ?, ?)
                ON CONFLICT(market_id) DO UPDATE SET q_yes=?, q_no=?
            ''', (market_id, q_yes, q_no, q_yes, q_no))
            
            # Invalidate odds cache when market state changes
            cache_key = f"market_odds_{market_id}"
            _cache.delete(cache_key)

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

def calculate_shares_lmsr_preview(amount, side, market_id):
    """
    Calculate expected shares using LMSR cost function WITHOUT updating market state.
    Used for preview/estimation purposes.
    
    LMSR Cost Function: C(q_yes, q_no) = b * ln(exp(q_yes/b) + exp(q_no/b))
    To buy shares: solve for shares where C(q_yes + shares, q_no) - C(q_yes, q_no) = amount
    """
    q_yes, q_no = get_market_state(market_id)
    b = Config.LMSR_B
    
    def cost_function(qy, qn):
        """LMSR cost function"""
        try:
            # Clamp to avoid overflow
            exp_yes_term = max(-700, min(700, qy / b))
            exp_no_term = max(-700, min(700, qn / b))
            exp_yes = math.exp(exp_yes_term)
            exp_no = math.exp(exp_no_term)
            return b * math.log(exp_yes + exp_no)
        except (OverflowError, ValueError):
            # Fallback for extreme values
            return max(qy, qn) + b
    
    # Calculate initial cost
    initial_cost = cost_function(q_yes, q_no)
    
    if side == 'YES':
        # Binary search for shares such that cost increase = amount
        # Start with approximation using current price
        current_yes_price, _ = calculate_market_price(market_id)
        shares_approx = amount / current_yes_price if current_yes_price > 0 else 0
        
        # Refine using binary search (more accurate for large bets)
        shares_low = shares_approx * 0.5
        shares_high = shares_approx * 2.0
        
        shares = shares_approx
        # Binary search for shares
        for _ in range(20):  # Max 20 iterations
            shares_mid = (shares_low + shares_high) / 2.0
            new_cost = cost_function(q_yes + shares_mid, q_no)
            cost_diff = new_cost - initial_cost
            
            if abs(cost_diff - amount) < 0.01:  # Close enough
                shares = shares_mid
                break
            elif cost_diff < amount:
                shares_low = shares_mid
            else:
                shares_high = shares_mid
        
        price_per_share = amount / shares if shares > 0 else current_yes_price
    else:  # NO
        # Same logic for NO side
        _, current_no_price = calculate_market_price(market_id)
        shares_approx = amount / current_no_price if current_no_price > 0 else 0
        
        shares_low = 0.0
        shares_high = shares_approx * 3.0
        
        shares = shares_approx
        for _ in range(30):
            shares_mid = (shares_low + shares_high) / 2.0
            new_cost = cost_function(q_yes, q_no + shares_mid)
            cost_diff = new_cost - initial_cost
            
            if abs(cost_diff - amount) < 0.001:
                shares = shares_mid
                break
            elif cost_diff < amount:
                shares_low = shares_mid
                shares = shares_mid
            else:
                shares_high = shares_mid
        
        price_per_share = amount / shares if shares > 0 else current_no_price
    
    shares = max(0, shares)
    return shares, price_per_share

def calculate_shares_lmsr(amount, side, market_id):
    """
    Calculate shares using LMSR cost function AND update market state.
    
    LMSR Cost Function: C(q_yes, q_no) = b * ln(exp(q_yes/b) + exp(q_no/b))
    To buy shares: solve for shares where C(q_yes + shares, q_no) - C(q_yes, q_no) = amount
    
    For small bets relative to liquidity, we use iterative approximation.
    """
    q_yes, q_no = get_market_state(market_id)
    b = Config.LMSR_B
    
    def cost_function(qy, qn):
        """LMSR cost function"""
        try:
            # Clamp to avoid overflow
            exp_yes_term = max(-700, min(700, qy / b))
            exp_no_term = max(-700, min(700, qn / b))
            exp_yes = math.exp(exp_yes_term)
            exp_no = math.exp(exp_no_term)
            return b * math.log(exp_yes + exp_no)
        except (OverflowError, ValueError):
            # Fallback for extreme values
            return max(qy, qn) + b
    
    # Calculate initial cost
    initial_cost = cost_function(q_yes, q_no)
    
    if side == 'YES':
        # Binary search for shares such that cost increase = amount
        # Start with approximation using current price
        current_yes_price, _ = calculate_market_price(market_id)
        shares_approx = amount / current_yes_price if current_yes_price > 0 else 0
        
        # Refine using binary search (more accurate for large bets)
        shares_low = shares_approx * 0.5
        shares_high = shares_approx * 2.0
        target_cost = initial_cost + amount
        
        # Binary search for shares
        shares = shares_approx
        for _ in range(20):  # Max 20 iterations
            shares_mid = (shares_low + shares_high) / 2.0
            new_cost = cost_function(q_yes + shares_mid, q_no)
            cost_diff = new_cost - initial_cost
            
            if abs(cost_diff - amount) < 0.01:  # Close enough
                shares = shares_mid
                break
            elif cost_diff < amount:
                shares_low = shares_mid
            else:
                shares_high = shares_mid
        
        new_q_yes = q_yes + shares
        update_market_state(market_id, new_q_yes, q_no)
        # Calculate average price per share
        final_cost = cost_function(new_q_yes, q_no)
        price_per_share = amount / shares if shares > 0 else current_yes_price
    else:  # NO
        # Same logic for NO side
        _, current_no_price = calculate_market_price(market_id)
        shares_approx = amount / current_no_price if current_no_price > 0 else 0
        
        shares_low = 0.0
        shares_high = shares_approx * 3.0
        
        shares = shares_approx
        for _ in range(30):
            shares_mid = (shares_low + shares_high) / 2.0
            new_cost = cost_function(q_yes, q_no + shares_mid)
            cost_diff = new_cost - initial_cost
            
            if abs(cost_diff - amount) < 0.001:
                shares = shares_mid
                break
            elif cost_diff < amount:
                shares_low = shares_mid
                shares = shares_mid
            else:
                shares_high = shares_mid
        
        new_q_no = q_no + shares
        update_market_state(market_id, q_yes, new_q_no)
        final_cost = cost_function(q_yes, new_q_no)
        price_per_share = amount / shares if shares > 0 else current_no_price
    
    shares = max(0, shares)
    return shares, price_per_share

def preview_trade(market_id, amount, side):
    """
    Service function to preview a trade without executing it.
    Returns expected shares and price per share.
    
    Args:
        market_id: Market ID
        amount: Trade amount in EURC
        side: 'YES' or 'NO'
    
    Returns:
        tuple: (shares, price_per_share) or raises ValueError if invalid
    """
    if amount <= 0:
        raise ValueError('Amount must be positive')
    if side not in ('YES', 'NO'):
        raise ValueError('Side must be YES or NO')
    
    shares, price_per_share = calculate_shares_lmsr_preview(amount, side, market_id)
    return shares, price_per_share
