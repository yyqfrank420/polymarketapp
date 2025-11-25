"""Bet processing service with thread-safe queue"""
import queue
import threading
import uuid
import time
import logging
import traceback
import os
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
worker_heartbeat = {'last_loop_time': None, 'loop_count': 0}  # Track worker activity
worker_heartbeat_lock = threading.Lock()

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
    logger.info(f"Thread ID: {threading.get_ident()}")
    logger.info(f"Database path: {Config.DATABASE_PATH}")
    logger.info(f"Database exists: {os.path.exists(Config.DATABASE_PATH)}")
    logger.info(f"Database readable: {os.access(Config.DATABASE_PATH, os.R_OK) if os.path.exists(Config.DATABASE_PATH) else 'N/A'}")
    logger.info(f"Database writable: {os.access(Config.DATABASE_PATH, os.W_OK) if os.path.exists(Config.DATABASE_PATH) else 'N/A'}")
    
    # Test database connection immediately
    try:
        test_conn = get_db()
        test_cursor = test_conn.cursor()
        test_cursor.execute('SELECT 1 as test')
        test_result = test_cursor.fetchone()
        logger.info(f"Initial database connection test: SUCCESS (result: {test_result})")
    except Exception as db_init_error:
        logger.error(f"Initial database connection test: FAILED - {db_init_error}", exc_info=True)
    
    loop_count = 0
    while True:
        loop_count += 1
        current_time = time.time()
        
        # Update heartbeat
        with worker_heartbeat_lock:
            worker_heartbeat['last_loop_time'] = current_time
            worker_heartbeat['loop_count'] = loop_count
        
        if loop_count % 10 == 0:  # Log every 10 loops
            logger.info(f"Bet worker loop #{loop_count}, queue size: {bet_queue.qsize()}")
        try:
            # Use timeout to allow periodic health checks
            try:
                logger.debug(f"Waiting for bet request from queue (size: {bet_queue.qsize()})...")
                bet_request = bet_queue.get(timeout=1.0)
                logger.info(f"Got bet request from queue: {bet_request.get('request_id')}")
            except queue.Empty:
                # Timeout - check if we should continue
                continue
            except Exception as queue_error:
                logger.error(f"Queue.get() error: {queue_error}", exc_info=True)
                time.sleep(1)
                continue
            
            if bet_request is None:  # Shutdown signal
                break
            
            logger.info(f"Processing bet request: {bet_request.get('request_id')}")
            
            request_id = bet_request['request_id']
            market_id = bet_request['market_id']
            wallet = bet_request['wallet']
            side = bet_request['side']
            amount = bet_request['amount']
            tx_hash = bet_request.get('tx_hash')
            signature = bet_request.get('signature')
            
            try:
                logger.info(f"Starting transaction for bet {request_id}")
                logger.info(f"Bet details: market_id={market_id}, wallet={wallet}, side={side}, amount={amount}")
                
                # Test database connection first
                try:
                    logger.info("Testing database connection...")
                    test_conn = get_db()
                    test_cursor = test_conn.cursor()
                    test_cursor.execute('SELECT 1 as test')
                    test_result = test_cursor.fetchone()
                    logger.info(f"Database connection test successful: {test_result}")
                except Exception as db_test_error:
                    logger.error(f"Database connection test failed: {db_test_error}", exc_info=True)
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    raise
                
                logger.info("Starting database transaction...")
                transaction_start_time = time.time()
                with db_transaction() as conn:
                    logger.info(f"Transaction started (took {time.time() - transaction_start_time:.3f}s)")
                    cursor = conn.cursor()
                    
                    # Check market status
                    logger.info(f"Checking market {market_id} status")
                    market_check_start = time.time()
                    try:
                        cursor.execute('SELECT status FROM markets WHERE id=?', (market_id,))
                        row = cursor.fetchone()
                        logger.info(f"Market query completed in {time.time() - market_check_start:.3f}s, result: {row}")
                    except Exception as market_query_error:
                        logger.error(f"Market query failed: {market_query_error}", exc_info=True)
                        logger.error(f"Traceback: {traceback.format_exc()}")
                        raise
                    
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
                    logger.info(f"Checking balance for wallet {wallet}")
                    balance_check_start = time.time()
                    try:
                        user_balance = get_user_balance(wallet)
                        logger.info(f"Balance check completed in {time.time() - balance_check_start:.3f}s")
                        logger.info(f"User balance: {user_balance}, required: {amount}")
                    except Exception as balance_error:
                        logger.error(f"Balance check failed: {balance_error}", exc_info=True)
                        logger.error(f"Traceback: {traceback.format_exc()}")
                        raise
                    
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
                    logger.info(f"Calculating shares for {side} side, amount {amount}")
                    lmsr_start = time.time()
                    try:
                        shares, price_per_share = calculate_shares_lmsr(amount, side, market_id)
                        logger.info(f"LMSR calculation completed in {time.time() - lmsr_start:.3f}s")
                        logger.info(f"Calculated: {shares} shares @ {price_per_share}")
                    except Exception as lmsr_error:
                        logger.error(f"LMSR calculation failed: {lmsr_error}", exc_info=True)
                        logger.error(f"Traceback: {traceback.format_exc()}")
                        raise
                    
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
                    logger.info(f"Inserting bet into database")
                    insert_start = time.time()
                    try:
                        cursor.execute('''
                            INSERT INTO bets (market_id, wallet, side, amount, shares, price_per_share, tx_hash, signature)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (market_id, wallet, side, amount, shares, price_per_share, tx_hash, signature))
                        
                        bet_id = cursor.lastrowid
                        logger.info(f"Bet insert completed in {time.time() - insert_start:.3f}s, bet_id: {bet_id}")
                    except Exception as insert_error:
                        logger.error(f"Bet insert failed: {insert_error}", exc_info=True)
                        logger.error(f"Traceback: {traceback.format_exc()}")
                        raise
                    
                    # Deduct balance
                    logger.info(f"Deducting {amount} from balance")
                    deduct_start = time.time()
                    try:
                        new_balance = update_user_balance(wallet, amount, 'deduct')
                        logger.info(f"Balance deduction completed in {time.time() - deduct_start:.3f}s")
                        logger.info(f"New balance: {new_balance}")
                    except Exception as deduct_error:
                        logger.error(f"Balance deduction failed: {deduct_error}", exc_info=True)
                        logger.error(f"Traceback: {traceback.format_exc()}")
                        raise
                    
                    total_time = time.time() - transaction_start_time
                    logger.info(f'Bet placed successfully in {total_time:.3f}s: market {market_id}, {side} €{amount:.2f} ({shares:.2f} shares @ €{price_per_share:.4f}) by {wallet}. New balance: €{new_balance:.2f}')
                    
                    # Store result
                    logger.info(f"Storing bet result for request_id: {request_id}")
                    result_store_start = time.time()
                    try:
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
                        logger.info(f"Result stored in {time.time() - result_store_start:.3f}s")
                    except Exception as result_error:
                        logger.error(f"Failed to store result: {result_error}", exc_info=True)
                        raise
                    
                    logger.info("Cleaning up old results...")
                    cleanup_old_results()
                    logger.info(f"Bet {request_id} processing COMPLETE")
            
            except Exception as e:
                logger.error(f'Bet processing error: {str(e)}', exc_info=True)
                import traceback
                logger.error(f'Traceback: {traceback.format_exc()}')
                with bet_results_lock:
                    bet_results[request_id] = {
                        'success': False,
                        'message': f'Failed to place bet: {str(e)}',
                        'timestamp': time.time()
                    }
            
            bet_queue.task_done()
        
        except Exception as e:
            logger.error(f'Bet worker error: {str(e)}', exc_info=True)
            import traceback
            logger.error(f'Worker traceback: {traceback.format_exc()}')
            # Continue processing - don't let worker die
            time.sleep(1)

# Start worker thread
bet_worker_thread = None

def ensure_worker_running():
    """Ensure bet worker thread is running, restart if needed"""
    global bet_worker_thread
    if bet_worker_thread is None or not bet_worker_thread.is_alive():
        logger.warning("Bet worker thread not running, starting...")
        bet_worker_thread = threading.Thread(target=bet_worker, daemon=True)
        bet_worker_thread.start()
        logger.info("Bet worker thread started")

# Start worker on module import
ensure_worker_running()

def process_bet_sync(market_id, wallet, side, amount, tx_hash=None, signature=None):
    """
    Process a bet synchronously (for PythonAnywhere compatibility - no threading)
    Returns: dict with 'success', 'bet_id', 'shares', 'price_per_share', etc.
    """
    request_id = str(uuid.uuid4())
    wallet = wallet.lower() if wallet else wallet
    
    try:
        logger.info(f"Processing bet synchronously: request_id={request_id}, market_id={market_id}, wallet={wallet}, side={side}, amount={amount}")
        
        with db_transaction() as conn:
            cursor = conn.cursor()
            
            # Check market status
            cursor.execute('SELECT status FROM markets WHERE id=?', (market_id,))
            row = cursor.fetchone()
            if not row:
                return {
                    'success': False,
                    'message': 'Market not found',
                    'request_id': request_id
                }
            
            if row['status'] != 'open':
                return {
                    'success': False,
                    'message': 'Market is not open',
                    'request_id': request_id
                }
            
            # Check user balance
            user_balance = get_user_balance(wallet)
            if user_balance < amount:
                return {
                    'success': False,
                    'message': f'Insufficient balance. You have €{user_balance:.2f}, need €{amount:.2f}',
                    'request_id': request_id
                }
            
            # Calculate shares using LMSR
            shares, price_per_share = calculate_shares_lmsr(amount, side, market_id)
            
            if shares <= 0:
                return {
                    'success': False,
                    'message': 'Invalid bet amount or market state',
                    'request_id': request_id
                }
            
            # Insert bet
            cursor.execute('''
                INSERT INTO bets (market_id, wallet, side, amount, shares, price_per_share, tx_hash, signature)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (market_id, wallet, side, amount, shares, price_per_share, tx_hash, signature))
            
            bet_id = cursor.lastrowid
            
            # Deduct balance
            new_balance = update_user_balance(wallet, amount, 'deduct')
            
            logger.info(f'Bet placed: market {market_id}, {side} €{amount:.2f} ({shares:.2f} shares @ €{price_per_share:.4f}) by {wallet}. New balance: €{new_balance:.2f}')
            
            # Store result for status checking
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
            
            return {
                'success': True,
                'request_id': request_id,
                'bet_id': bet_id,
                'shares': shares,
                'price_per_share': price_per_share,
                'amount': amount,
                'side': side,
                'market_id': market_id
            }
    
    except Exception as e:
        logger.error(f'Bet processing error: {str(e)}', exc_info=True)
        with bet_results_lock:
            bet_results[request_id] = {
                'success': False,
                'message': f'Failed to place bet: {str(e)}',
                'timestamp': time.time()
            }
        return {
            'success': False,
            'message': f'Failed to place bet: {str(e)}',
            'request_id': request_id
        }

def queue_bet(market_id, wallet, side, amount, tx_hash=None, signature=None):
    """
    Queue a bet for processing (DEPRECATED on PythonAnywhere - use process_bet_sync instead)
    On PythonAnywhere, threading doesn't work, so this just processes synchronously
    """
    # PythonAnywhere doesn't support threading - process immediately
    result = process_bet_sync(market_id, wallet, side, amount, tx_hash, signature)
    # Return format compatible with old queue system
    return result['request_id'], 0  # queue_position is always 0 for sync processing

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

