"""Admin routes"""
from flask import Blueprint, render_template, request, jsonify
import logging
from utils.database import get_db, db_transaction, _row_to_dict
from utils.validators import standard_error_response, standard_success_response
from services.user_service import get_user_balance, update_user_balance
from services.market_service import calculate_market_price
from config import Config

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin')
def admin_page():
    """Render the admin dashboard"""
    return render_template('admin.html')

@admin_bp.route('/admin/create-market')
def admin_create_market_page():
    """Render the admin market creation page"""
    return render_template('admin_create_market.html')

@admin_bp.route('/admin/resolve')
def admin_resolve_page():
    """Render the admin resolution page"""
    return render_template('admin_resolve.html')

@admin_bp.route('/api/markets/<int:market_id>/resolve', methods=['POST'])
def resolve_market(market_id):
    """Resolve a market and automatically distribute payouts"""
    try:
        data = request.get_json() or {}
        outcome = (data.get('outcome') or '').strip().upper()
        if outcome not in ('YES', 'NO'):
            return standard_error_response('Outcome must be YES or NO', 400)

        with db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT status FROM markets WHERE id=?', (market_id,))
            row = cursor.fetchone()
            if not row:
                return standard_error_response('Market not found', 404)
            if row['status'] == 'resolved':
                return standard_error_response('Market already resolved', 400)
            cursor.execute('UPDATE markets SET status="resolved", resolution=? WHERE id=?', (outcome, market_id))
        
        logger.info(f'Market {market_id} resolved as {outcome}')
        
        # Automatically distribute payouts to winners
        try:
            conn = get_db()
            cursor = conn.cursor()
            
            # Get all bets for this market
            cursor.execute('SELECT wallet, side, shares, amount FROM bets WHERE market_id=?', (market_id,))
            bets = cursor.fetchall()
            
            payouts_distributed = {}
            winners_count = 0
            total_payout = 0
            
            # Calculate and distribute payouts with 2% fee on profits
            total_fees_collected = 0
            for bet in bets:
                wallet = bet['wallet']
                if bet['side'] == outcome:
                    # Winner! Each share pays $1.00
                    gross_payout = bet['shares'] * 1.0
                    cost_basis = bet['amount']  # What they originally paid
                    
                    # Calculate net profit
                    net_profit = max(0, gross_payout - cost_basis)
                    
                    # Apply 2% fee on profits only (like Polymarket)
                    fee = net_profit * Config.PROFIT_FEE_RATE
                    
                    # Final payout after fee
                    final_payout = gross_payout - fee
                    
                    # Credit their balance
                    new_balance = update_user_balance(wallet, final_payout, 'add')
                    
                    # Track totals
                    if wallet not in payouts_distributed:
                        payouts_distributed[wallet] = 0
                    payouts_distributed[wallet] += final_payout
                    winners_count += 1
                    total_payout += final_payout
                    total_fees_collected += fee
                    
                    logger.info(f'💰 Payout: {wallet[:10]}... | Gross: {gross_payout:.2f} USDC | Fee: {fee:.2f} USDC (2%) | Net: {final_payout:.2f} USDC | Balance: {new_balance:.2f} USDC')
            
            logger.info(f'✅ Market {market_id} resolved as {outcome}. Distributed {total_payout:.2f} USDC to {len(payouts_distributed)} winner(s) ({winners_count} winning bets). Fees collected: {total_fees_collected:.2f} USDC (2%)')
            
            return standard_success_response({
                'outcome': outcome,
                'payouts_distributed': True,
                'total_payout': round(total_payout, 2),
                'winners_count': len(payouts_distributed),
                'total_fees': round(total_fees_collected, 2)
            })
            
        except Exception as payout_error:
            logger.error(f'Payout distribution error for market {market_id}: {str(payout_error)}')
            # Market is still resolved, but payouts failed
            return standard_success_response({
                'outcome': outcome,
                'payouts_distributed': False,
                'error': 'Market resolved but payout distribution failed'
            })
        
    except Exception as e:
        logger.error(f'Resolve market error: {str(e)}')
        return standard_error_response('Failed to resolve market', 500)

@admin_bp.route('/api/markets/<int:market_id>/payouts', methods=['GET'])
def get_market_payouts(market_id):
    """Calculate payouts for resolved market"""
    try:
        conn = get_db()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT status, resolution FROM markets WHERE id=?', (market_id,))
            market = cursor.fetchone()
            if not market:
                return standard_error_response('Market not found', 404)
            
            if market['status'] != 'resolved':
                return standard_error_response('Market not resolved yet', 400)
            
            winning_side = market['resolution']
            cursor.execute('SELECT wallet, side, amount, shares, price_per_share FROM bets WHERE market_id=?', (market_id,))
            bets = [dict(_row_to_dict(r)) for r in cursor.fetchall()]
            
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
                    bet_payout = bet_shares * 1.0
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
                    payouts[wallet]['bets'].append({
                        'side': bet['side'],
                        'amount': bet_amount,
                        'shares': bet_shares,
                        'price_per_share': bet['price_per_share'] or 0,
                        'result': 'lost',
                        'payout': 0
                    })
            
            # Credit payouts
            for wallet_data in payouts.values():
                wallet_data['profit'] = wallet_data['payout'] - wallet_data['total_bet']
                if wallet_data['payout'] > 0:
                    update_user_balance(wallet_data['wallet'], wallet_data['payout'], 'add')
                    logger.info(f'Credited {wallet_data["wallet"]} with {wallet_data["payout"]:.2f} USDC payout')
            
            return jsonify({
                'market_id': market_id,
                'resolution': winning_side,
                'total_amount_bet': total_amount_bet,
                'total_payout': total_payout,
                'payouts': list(payouts.values())
            }), 200
        finally:
            pass
    except Exception as e:
        logger.error(f'Payouts calculation error: {str(e)}')
        return standard_error_response('Failed to calculate payouts', 500)

@admin_bp.route('/api/user/<wallet>/credit', methods=['POST'])
def credit_user(wallet):
    """Manually credit user (admin/testing)"""
    try:
        data = request.get_json() or {}
        amount = float(data.get('amount', 0))
        
        if amount <= 0:
            return standard_error_response('Amount must be positive', 400)
        
        # Validate wallet address format (basic check)
        if not wallet.startswith('0x') or len(wallet) < 10:
            return standard_error_response('Invalid wallet address format', 400)
        
        get_user_balance(wallet)  # Ensure user exists
        new_balance = update_user_balance(wallet, amount, 'add')
        
        logger.info(f'💰 Admin credited {wallet} with {amount:.2f} USDC. New balance: {new_balance:.2f} USDC')
        
        return jsonify({
            'success': True,
            'wallet': wallet,
            'amount': round(amount, 2),
            'new_balance': round(new_balance, 2),
            'message': f'Successfully credited {amount:.2f} USDC to {wallet[:10]}...'
        }), 200
    except Exception as e:
        logger.error(f'Credit user error: {str(e)}')
        return standard_error_response('Failed to credit user', 500)

@admin_bp.route('/api/admin/users', methods=['GET'])
def get_all_users():
    """Get all users with their stats"""
    try:
        conn = get_db()
        try:
            cursor = conn.cursor()
            
            # Get all users with their bet statistics and auth status
            cursor.execute('''
                SELECT 
                    u.wallet,
                    u.balance,
                    u.created_at,
                    u.last_login,
                    COALESCE(u.auth_status, 'unverified') as auth_status,
                    COUNT(DISTINCT b.id) as total_bets,
                    COALESCE(SUM(b.amount), 0) as total_bet_amount,
                    COUNT(DISTINCT CASE WHEN b.shares > 0 AND m.status = 'open' THEN b.id END) as open_positions
                FROM users u
                LEFT JOIN bets b ON u.wallet = b.wallet
                LEFT JOIN markets m ON b.market_id = m.id
                GROUP BY u.wallet, u.balance, u.created_at, u.last_login, u.auth_status
                ORDER BY u.created_at DESC
            ''')
            
            users = []
            for row in cursor.fetchall():
                user_data = dict(_row_to_dict(row))
                users.append({
                    'wallet': user_data['wallet'],
                    'balance': round(user_data['balance'] or 0.0, 2),
                    'total_bets': user_data['total_bets'] or 0,
                    'total_bet_amount': round(user_data['total_bet_amount'] or 0.0, 2),
                    'open_positions': user_data['open_positions'] or 0,
                    'created_at': user_data['created_at'],
                    'last_login': user_data['last_login'],
                    'auth_status': user_data.get('auth_status', 'unverified')
                })
            
            return jsonify({'users': users}), 200
        finally:
            pass
    except Exception as e:
        logger.error(f'Get all users error: {str(e)}')
        return standard_error_response('Failed to get users', 500)

@admin_bp.route('/api/admin/users/<wallet>/delete', methods=['DELETE'])
def delete_user(wallet):
    """Delete a user and automatically sell their open positions"""
    try:
        wallet = wallet.strip()
        if not wallet or not wallet.startswith('0x'):
            return standard_error_response('Invalid wallet address', 400)
        
        with db_transaction() as conn:
            cursor = conn.cursor()
            
            # Get all open positions (bets with shares > 0 in open markets)
            cursor.execute('''
                SELECT b.id, b.market_id, b.side, b.shares, b.amount
                FROM bets b
                JOIN markets m ON b.market_id = m.id
                WHERE b.wallet = ? AND m.status = 'open' AND b.shares > 0
            ''', (wallet,))
            
            open_positions = cursor.fetchall()
            
            # Automatically sell all open positions
            for position in open_positions:
                bet_id = position['id']
                market_id = position['market_id']
                side = position['side']
                shares = position['shares']
                
                try:
                    # Get current price
                    current_yes_price, current_no_price = calculate_market_price(market_id)
                    current_price = current_yes_price if side == 'YES' else current_no_price
                    
                    # Calculate sell value
                    sell_value = shares * current_price
                    
                    # Update market state: decrease q_yes or q_no
                    cursor.execute('SELECT q_yes, q_no FROM market_state WHERE market_id=?', (market_id,))
                    state_row = cursor.fetchone()
                    if state_row:
                        q_yes = state_row['q_yes'] or 0
                        q_no = state_row['q_no'] or 0
                        
                        if side == 'YES':
                            new_q_yes = max(0, q_yes - shares)
                            cursor.execute('UPDATE market_state SET q_yes=?, q_no=? WHERE market_id=?', 
                                         (new_q_yes, q_no, market_id))
                        else:  # NO
                            new_q_no = max(0, q_no - shares)
                            cursor.execute('UPDATE market_state SET q_yes=?, q_no=? WHERE market_id=?', 
                                         (q_yes, new_q_no, market_id))
                    
                    logger.info(f'Auto-sold {shares:.2f} {side} shares for user {wallet[:10]}... in market {market_id}')
                except Exception as e:
                    logger.error(f'Error auto-selling position {bet_id}: {str(e)}')
                    # Continue with other positions even if one fails
            
            # Delete all bets for this user
            cursor.execute('DELETE FROM bets WHERE wallet=?', (wallet,))
            bets_deleted = cursor.rowcount
            
            # Delete user record
            cursor.execute('DELETE FROM users WHERE wallet=?', (wallet,))
            user_deleted = cursor.rowcount
            
            if user_deleted == 0:
                return standard_error_response('User not found', 404)
            
            logger.info(f'Deleted user {wallet[:10]}... ({bets_deleted} bets removed, {len(open_positions)} positions auto-sold)')
        
        return jsonify({
            'success': True,
            'message': f'User deleted successfully. {len(open_positions)} positions auto-sold, {bets_deleted} bets removed.',
            'positions_sold': len(open_positions),
            'bets_deleted': bets_deleted
        }), 200
        
    except Exception as e:
        logger.error(f'Delete user error: {str(e)}', exc_info=True)
        return standard_error_response(f'Failed to delete user: {str(e)}', 500)

@admin_bp.route('/api/activity/recent', methods=['GET'])
def get_recent_activity():
    """Get recent betting activity"""
    try:
        conn = get_db()
        try:
            cursor = conn.cursor()
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
                
                try:
                    current_yes_price, current_no_price = calculate_market_price(market_id)
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
                        'created_at': bet['created_at']
                    })
                except ValueError:
                    continue
            
            return jsonify({'activity': recent_bets}), 200
        finally:
            pass
    except Exception as e:
        logger.error(f'Recent activity error: {str(e)}')
        return jsonify({'activity': []}), 200

@admin_bp.route('/api/markets/<int:market_id>/sell', methods=['POST'])
def sell_shares(market_id):
    """Sell shares back to market"""
    try:
        data = request.get_json() or {}
        wallet = (data.get('wallet') or '').strip()
        bet_id = int(data.get('bet_id') or 0)
        shares_to_sell = float(data.get('shares') or 0)

        if not wallet or bet_id <= 0 or shares_to_sell <= 0:
            return standard_error_response('Invalid parameters', 400)

        with db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT b.id, b.market_id, b.side, b.shares, b.amount, b.price_per_share,
                       m.status
                FROM bets b
                JOIN markets m ON b.market_id = m.id
                WHERE b.id = ? AND b.wallet = ? AND m.status = 'open'
            ''', (bet_id, wallet))
            
            bet_row = cursor.fetchone()
            if not bet_row:
                return standard_error_response('Bet not found or market is not open', 404)
            
            bet = dict(_row_to_dict(bet_row))
            current_shares = bet['shares'] or 0
            
            if shares_to_sell > current_shares:
                return standard_error_response(f'Cannot sell more than {current_shares:.2f} shares', 400)
            
            try:
                current_yes_price, current_no_price = calculate_market_price(market_id)
                current_price = current_yes_price if bet['side'] == 'YES' else current_no_price
            except ValueError:
                return standard_error_response('Failed to get current price', 500)
            
            sell_value = shares_to_sell * current_price
            remaining_shares = current_shares - shares_to_sell
            remaining_amount = bet['amount'] * (remaining_shares / current_shares) if current_shares > 0 else 0
            
            if remaining_shares < 0.01:
                cursor.execute('DELETE FROM bets WHERE id=?', (bet_id,))
            else:
                cursor.execute('UPDATE bets SET shares = ?, amount = ? WHERE id = ?', 
                             (remaining_shares, remaining_amount, bet_id))
            
            # Update market state: decrease q_yes or q_no when shares are sold back
            # Do this within the same transaction to avoid nested transaction issues
            cursor.execute('SELECT q_yes, q_no FROM market_state WHERE market_id=?', (market_id,))
            state_row = cursor.fetchone()
            if state_row:
                q_yes = state_row['q_yes'] or 0
                q_no = state_row['q_no'] or 0
            else:
                # Initialize if doesn't exist (shouldn't happen, but safety check)
                from config import Config
                q_yes = Config.LMSR_BUFFER
                q_no = Config.LMSR_BUFFER
                cursor.execute('INSERT INTO market_state (market_id, q_yes, q_no) VALUES (?, ?, ?)', 
                             (market_id, q_yes, q_no))
            
            if bet['side'] == 'YES':
                new_q_yes = max(0, q_yes - shares_to_sell)  # Prevent negative
                cursor.execute('''
                    UPDATE market_state SET q_yes=?, q_no=? WHERE market_id=?
                ''', (new_q_yes, q_no, market_id))
            else:  # NO
                new_q_no = max(0, q_no - shares_to_sell)  # Prevent negative
                cursor.execute('''
                    UPDATE market_state SET q_yes=?, q_no=? WHERE market_id=?
                ''', (q_yes, new_q_no, market_id))
            
            update_user_balance(wallet, sell_value, 'add')
        
        return jsonify({
            'success': True,
            'message': f'Sold {shares_to_sell:.2f} shares for ${sell_value:.2f}',
            'shares_sold': round(shares_to_sell, 2),
            'sell_value': round(sell_value, 2),
            'remaining_shares': round(remaining_shares, 2) if remaining_shares >= 0.01 else 0,
            'current_price': round(current_price, 4)
        }), 200
        
    except ValueError as e:
        logger.error(f'Sell shares validation error: {str(e)}')
        return standard_error_response(f'Invalid request: {str(e)}', 400)
    except Exception as e:
        logger.error(f'Sell shares error: {str(e)}', exc_info=True)
        return standard_error_response(f'Failed to sell shares: {str(e)}', 500)

