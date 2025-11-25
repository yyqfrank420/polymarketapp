"""Bet processing service with thread-safe queue"""
import queue
import threading
import uuid
import time
import logging
from collections import OrderedDict
from utils.database import get_db, db_transaction
from services.user_service import get_user_balance, update_user_balance
from services.market_service import calculate_shares_lmsr
from config import Config

logger = logging.getLogger(__name__)

# Thread-safe bet queue and results
bet_queue = queue.Queue()
bet_results_lock = threading.Lock()
bet_results = OrderedDict()

def cleanup_old_results():
    """Clean up old bet results"""
    current_time = time.time()
    with bet_results_lock:
        to_remove = [
            rid for rid, result in bet_results.items()
            if current_time - result.get('timestamp', 0) > Config.BET_RESULT_TTL
        ]
        for rid in to_remove:
            bet_results.pop(rid, None)
        
        # Also limit total size
        while len(bet_results) > Config.MAX_BET_RESULTS:
            bet_results.popitem(last=False)

def bet_worker():
    """Background worker that processes bets sequentially"""
    logger.info("Bet worker thread started")
    
    while True:
        try:
            # Wait for bet request (with timeout for graceful shutdown)
            try:
                bet_request = bet_queue.get(timeout=1.0)
            except queue.Empty:
                continue
            
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
                with db_transaction() as conn:
                    cursor = conn.cursor()
                    
                    # Check market status
                    cursor.execute('SELECT status FROM markets WHERE id=?', (market_id,))
                    row = cursor.fetchone()
                    
                    if not row:
                        with bet_results_lock:
                            bet_results[request_id] = {
                                'success': False,
                                'message': 'Market not found',
                                'timestamp': time.time()
                            }
                        bet_queue.task_done()
                        continue
                    
                    if row['status'] != 'open':
                        with bet_results_lock:
                            bet_results[request_id] = {
                                'success': False,
                                'message': 'Market is not open',
                                'timestamp': time.time()
                            }
                        bet_queue.task_done()
                        continue
                    
                    # Check user balance
                    user_balance = get_user_balance(wallet)
                    if user_balance < amount:
                        with bet_results_lock:
                            bet_results[request_id] = {
                                'success': False,
                                'message': f'Insufficient balance. You have €{user_balance:.2f}, need €{amount:.2f}',
                                'timestamp': time.time()
                            }
                        bet_queue.task_done()
                        continue
                    
                    # Calculate shares using LMSR
                    shares, price_per_share = calculate_shares_lmsr(amount, side, market_id)
                    
                    if shares <= 0:
                        with bet_results_lock:
                            bet_results[request_id] = {
                                'success': False,
                                'message': 'Invalid bet amount or market state',
                                'timestamp': time.time()
                            }
                        bet_queue.task_done()
                        continue
                    
                    # Insert bet
                    cursor.execute('''
                        INSERT INTO bets (market_id, wallet, side, amount, shares, price_per_share, tx_hash, signature)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (market_id, wallet, side, amount, shares, price_per_share, tx_hash, signature))
                    
                    bet_id = cursor.lastrowid
                    
                    # Deduct balance
                    new_balance = update_user_balance(wallet, amount, 'deduct')
                    
                    logger.info(f'Bet placed: market {market_id}, {side} €{amount:.2f} ({shares:.2f} shares @ €{price_per_share:.4f}) by {wallet}')
                    
                    # Store result
                    with bet_results_lock:
                        bet_results[request_id] = {
                            'success': True,
                            'bet_id': bet_id,
                            'shares': shares,
                            'price_per_share': price_per_share,
                            'amount': amount,
                            'side': side,
                            'market_id': market_id,
                            'timestamp': time.time()
                        }
                    
                    cleanup_old_results()
            
            except Exception as e:
                logger.error(f'Bet processing error: {str(e)}', exc_info=True)
                with bet_results_lock:
                    bet_results[request_id] = {
                        'success': False,
                        'message': f'Failed to place bet: {str(e)}',
                        'timestamp': time.time()
                    }
            
            bet_queue.task_done()
        
        except Exception as e:
            logger.error(f'Bet worker error: {str(e)}', exc_info=True)
            time.sleep(1)

# Start worker thread
bet_worker_thread = None

def ensure_worker_running():
    """Ensure bet worker thread is running, restart if needed"""
    global bet_worker_thread
    if bet_worker_thread is None or not bet_worker_thread.is_alive():
        logger.info("Starting bet worker thread...")
        bet_worker_thread = threading.Thread(target=bet_worker, daemon=True)
        bet_worker_thread.start()

# Start worker on module import
ensure_worker_running()

def queue_bet(market_id, wallet, side, amount, tx_hash=None, signature=None):
    """
    Queue a bet for processing by the background worker.
    Returns (request_id, queue_position) for status polling.
    """
    request_id = str(uuid.uuid4())
    wallet = wallet.lower() if wallet else wallet
    
    # Get queue position before adding
    queue_position = bet_queue.qsize()
    
    bet_queue.put({
        'request_id': request_id,
        'market_id': market_id,
        'wallet': wallet,
        'side': side,
        'amount': amount,
        'tx_hash': tx_hash,
        'signature': signature
    })
    
    return request_id, queue_position

def get_bet_result(request_id):
    """Get bet result by request_id"""
    with bet_results_lock:
        return bet_results.pop(request_id, None)  # Remove after fetching

def undo_bet(bet_id, wallet):
    """
    Undo/cancel a bet - refund user and reverse market state
    
    Returns:
        dict: {
            'success': bool,
            'message': str,
            'refunded_amount': float,
            'new_balance': float
        } or None if bet not found/unauthorized
    """
    from services.user_service import update_user_balance
    from services.market_service import get_market_state, update_market_state
    
    try:
        with db_transaction() as conn:
            cursor = conn.cursor()
            
            # Get bet details
            wallet = wallet.lower() if wallet else wallet
            cursor.execute('''
                SELECT market_id, wallet, side, amount, shares, price_per_share
                FROM bets WHERE id=? AND LOWER(wallet)=?
            ''', (bet_id, wallet))
            bet = cursor.fetchone()
            
            if not bet:
                return None  # Bet not found or unauthorized
            
            # Check if market is still open
            cursor.execute('SELECT status FROM markets WHERE id=?', (bet['market_id'],))
            market = cursor.fetchone()
            if not market or market['status'] != 'open':
                return {
                    'success': False,
                    'message': 'Cannot undo bet - market is not open'
                }
            
            # Reverse market state (enforce buffer minimum)
            from config import Config
            q_yes, q_no = get_market_state(bet['market_id'])
            if bet['side'] == 'YES':
                new_q_yes = max(Config.LMSR_BUFFER, q_yes - bet['shares'])
                update_market_state(bet['market_id'], new_q_yes, q_no)
            else:  # NO
                new_q_no = max(Config.LMSR_BUFFER, q_no - bet['shares'])
                update_market_state(bet['market_id'], q_yes, new_q_no)
            
            # Refund user
            new_balance = update_user_balance(wallet, bet['amount'], 'add')
            
            # Delete bet
            cursor.execute('DELETE FROM bets WHERE id=?', (bet_id,))
            
            logger.info(f'Bet {bet_id} undone: refunded {bet["amount"]:.2f} to {wallet}')
            
            return {
                'success': True,
                'message': f'Bet undone. Refunded {bet["amount"]:.2f} EURC',
                'refunded_amount': bet['amount'],
                'new_balance': new_balance
            }
            
    except Exception as e:
        logger.error(f'Undo bet error: {str(e)}')
        return {
            'success': False,
            'message': f'Failed to undo bet: {str(e)}'
        }
