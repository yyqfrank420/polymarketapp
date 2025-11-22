"""API Routes - Clean microservices architecture"""
from flask import Blueprint, request, jsonify
import logging
from datetime import datetime
from utils.database import get_db, db_transaction, _row_to_dict
from utils.validators import (
    validate_wallet_address, validate_amount, validate_side,
    standard_error_response, standard_success_response
)
from services.market_service import calculate_market_price, calculate_shares_lmsr
from services.user_service import get_user_balance, update_user_balance
from services.bet_service import queue_bet, get_bet_result
from services.blockchain_service import get_blockchain_service
# Import chatbot_service lazily to avoid premature singleton creation
# from services.chatbot_service import get_chatbot_service  # Moved to function scope
from config import Config

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__, url_prefix='/api')

# ========== MARKETS API ==========
@api_bp.route('/markets', methods=['GET'])
def list_markets():
    """List all open markets with LMSR prices (excludes resolved markets)"""
    try:
        conn = get_db()
        try:
            cursor = conn.cursor()
            # Only show open markets on homepage
            cursor.execute('SELECT * FROM markets WHERE status="open" ORDER BY created_at DESC')
            markets = [dict(_row_to_dict(r)) for r in cursor.fetchall()]
            
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
                
                try:
                    yes_price, no_price = calculate_market_price(m['id'])
                    m['yes_price'] = yes_price
                    m['no_price'] = no_price
                    m['yes_price_cents'] = round(yes_price * 100, 2)
                    m['no_price_cents'] = round(no_price * 100, 2)
                except ValueError:
                    m['yes_price'] = 0.5
                    m['no_price'] = 0.5
                    m['yes_price_cents'] = 50.0
                    m['no_price_cents'] = 50.0
            
            return jsonify({'markets': markets}), 200
        finally:
            pass
    except Exception as e:
        logger.error(f'Markets list error: {str(e)}')
        return jsonify({'markets': []}), 200

@api_bp.route('/markets', methods=['POST'])
def create_market():
    """Create a new market"""
    try:
        data = request.get_json() or {}
        question = (data.get('question') or '').strip()
        description = (data.get('description') or '').strip()
        image_url = (data.get('image_url') or '').strip()
        category = (data.get('category') or '').strip()
        end_date = (data.get('end_date') or '').strip()
        created_by = (data.get('created_by') or '').strip()
        
        if not question:
            return standard_error_response('Question is required', 400)
        
        with db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO markets (question, description, image_url, category, end_date, created_by) 
                VALUES (?,?,?,?,?,?)
            ''', (question, description, image_url, category, end_date, created_by))
            market_id = cursor.lastrowid
            
            cursor.execute('INSERT INTO market_state (market_id, q_yes, q_no) VALUES (?, 0.0, 0.0)', (market_id,))
        
        logger.info(f'Created market {market_id}: {question} by {created_by}')
        return standard_success_response({'market_id': market_id}, status_code=201)
    except Exception as e:
        logger.error(f'Create market error: {str(e)}')
        return standard_error_response('Failed to create market', 500)

@api_bp.route('/markets/<int:market_id>', methods=['GET'])
def get_market(market_id):
    """Get market details"""
    try:
        conn = get_db()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM markets WHERE id=?', (market_id,))
            row = cursor.fetchone()
            if not row:
                return standard_error_response('Market not found', 404)
            
            market = dict(_row_to_dict(row))
            cursor.execute('SELECT side, amount FROM bets WHERE market_id=?', (market_id,))
            bets = [dict(_row_to_dict(r)) for r in cursor.fetchall()]
            cursor.execute('''SELECT
                               SUM(CASE WHEN side="YES" THEN amount ELSE 0 END) as yes_total,
                               SUM(CASE WHEN side="NO" THEN amount ELSE 0 END) as no_total,
                               COUNT(*) as bet_count
                             FROM bets WHERE market_id=?''', (market_id,))
            agg = cursor.fetchone()
            market['yes_total'] = agg['yes_total'] or 0.0
            market['no_total'] = agg['no_total'] or 0.0
            market['bet_count'] = agg['bet_count'] or 0
            
            try:
                yes_price, no_price = calculate_market_price(market_id)
                market['yes_price'] = yes_price
                market['no_price'] = no_price
                market['yes_price_cents'] = round(yes_price * 100, 2)
                market['no_price_cents'] = round(no_price * 100, 2)
            except ValueError:
                market['yes_price'] = 0.5
                market['no_price'] = 0.5
                market['yes_price_cents'] = 50.0
                market['no_price_cents'] = 50.0
            
            return jsonify({'market': market, 'bets': bets}), 200
        finally:
            pass
    except Exception as e:
        logger.error(f'Get market error: {str(e)}')
        return standard_error_response('Failed to fetch market', 500)

@api_bp.route('/markets/resolved', methods=['GET'])
def list_resolved_markets():
    """List all resolved markets"""
    try:
        conn = get_db()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM markets WHERE status="resolved" ORDER BY created_at DESC')
            markets = [dict(_row_to_dict(r)) for r in cursor.fetchall()]
            
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
                
                # For resolved markets, prices are final
                if m['resolution'] == 'YES':
                    m['yes_price'] = 1.0
                    m['no_price'] = 0.0
                    m['yes_price_cents'] = 100.0
                    m['no_price_cents'] = 0.0
                elif m['resolution'] == 'NO':
                    m['yes_price'] = 0.0
                    m['no_price'] = 1.0
                    m['yes_price_cents'] = 0.0
                    m['no_price_cents'] = 100.0
                else:
                    m['yes_price'] = 0.5
                    m['no_price'] = 0.5
                    m['yes_price_cents'] = 50.0
                    m['no_price_cents'] = 50.0
            
            return jsonify({'markets': markets}), 200
        finally:
            pass
    except Exception as e:
        logger.error(f'Resolved markets list error: {str(e)}')
        return jsonify({'markets': []}), 200

@api_bp.route('/markets/<int:market_id>/price', methods=['GET'])
def get_market_price(market_id):
    """Get current market prices"""
    try:
        yes_price, no_price = calculate_market_price(market_id)
        return jsonify({
            'yes_price': round(yes_price, 4),
            'no_price': round(no_price, 4),
            'yes_price_cents': round(yes_price * 100, 2),
            'no_price_cents': round(no_price * 100, 2)
        }), 200
    except ValueError as e:
        return standard_error_response(str(e), 404)
    except Exception as e:
        logger.error(f'Get market price error: {str(e)}')
        return standard_error_response('Failed to get prices', 500)

# ========== BETTING API ==========
@api_bp.route('/markets/<int:market_id>/bet', methods=['POST'])
def place_bet(market_id):
    """Queue bet for processing"""
    try:
        data = request.get_json() or {}
        wallet = (data.get('wallet') or '').strip()
        side = (data.get('side') or '').strip().upper()
        amount = data.get('amount')
        tx_hash = (data.get('tx_hash') or '').strip() or None
        signature = (data.get('signature') or '').strip() or None

        # Validation
        if not validate_side(side):
            return standard_error_response('Side must be YES or NO', 400)
        if not validate_amount(amount):
            return standard_error_response('Amount must be positive', 400)
        if not validate_wallet_address(wallet):
            return standard_error_response('Invalid wallet address', 400)

        amount = float(amount)

        # Quick market check
        conn = get_db()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT status FROM markets WHERE id=?', (market_id,))
            row = cursor.fetchone()
            if not row:
                return standard_error_response('Market not found', 404)
            if row['status'] != 'open':
                return standard_error_response('Market is not open', 400)
        finally:
            pass

        # Queue bet
        request_id = queue_bet(market_id, wallet, side, amount, tx_hash, signature)
        
        return jsonify({
            'success': True,
            'status': 'queued',
            'request_id': request_id,
            'message': 'Your bet is being processed...'
        }), 202
        
    except Exception as e:
        logger.error(f'Place bet error: {str(e)}')
        return standard_error_response('Failed to queue bet', 500)

@api_bp.route('/bets/<request_id>/status', methods=['GET'])
def check_bet_status(request_id):
    """Check bet processing status"""
    result = get_bet_result(request_id)
    if result:
        return jsonify(result), 200
    else:
        return jsonify({
            'success': False,
            'status': 'processing',
            'message': 'Bet is still being processed...'
        }), 202

# ========== USER API ==========
@api_bp.route('/user/<wallet>/balance', methods=['GET'])
def get_user_balance_api(wallet):
    """Get user balance"""
    try:
        balance = get_user_balance(wallet)
        is_new_user = balance == Config.INITIAL_FAKE_CRYPTO_BALANCE
        
        return jsonify({
            'wallet': wallet,
            'balance': round(balance, 2),
            'is_new_user': is_new_user
        }), 200
    except Exception as e:
        logger.error(f'Get balance error: {str(e)}')
        return standard_error_response('Failed to get balance', 500)

@api_bp.route('/user/<wallet>/bets', methods=['GET'])
def get_user_bets(wallet):
    """Get user's bets"""
    try:
        conn = get_db()
        try:
            cursor = conn.cursor()
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
                
                if bet_info['status'] == 'resolved':
                    resolution = bet_info['resolution']
                    shares = bet_info['shares'] or 0
                    
                    if bet_info['side'] == resolution:
                        bet_info['result'] = 'won'
                        bet_info['payout'] = round(shares * 1.0, 2)
                        bet_info['profit'] = round(bet_info['payout'] - bet_info['amount'], 2)
                    else:
                        bet_info['result'] = 'lost'
                        bet_info['payout'] = 0
                        bet_info['profit'] = -bet_info['amount']
                else:
                    bet_info['result'] = 'pending'
                    bet_info['payout'] = None
                    bet_info['profit'] = None
                    
                    try:
                        current_yes_price, current_no_price = calculate_market_price(bet_info['market_id'])
                        current_price = current_yes_price if bet_info['side'] == 'YES' else current_no_price
                        shares = bet_info['shares'] or 0
                        current_value = shares * current_price
                        unrealized_profit = current_value - bet_info['amount']
                        
                        bet_info['current_price'] = round(current_price, 4)
                        bet_info['current_value'] = round(current_value, 2)
                        bet_info['unrealized_profit'] = round(unrealized_profit, 2)
                    except ValueError:
                        bet_info['current_price'] = None
                        bet_info['current_value'] = None
                        bet_info['unrealized_profit'] = None
                
                bets.append(bet_info)
            
            return jsonify({'bets': bets}), 200
        finally:
            pass
    except Exception as e:
        logger.error(f'Get user bets error: {str(e)}')
        return jsonify({'bets': []}), 200

# ========== BLOCKCHAIN API ==========
@api_bp.route('/admin/markets/blockchain', methods=['POST'])
def create_market_blockchain():
    """Create market on blockchain AND database"""
    try:
        blockchain_service = get_blockchain_service()
        if not blockchain_service.is_configured():
            return standard_error_response('Blockchain not configured. Please deploy contract first.', 400)
        
        data = request.get_json() or {}
        question = (data.get('question') or '').strip()
        description = (data.get('description') or '').strip()
        end_date = (data.get('end_date') or '').strip()
        
        if not question:
            return standard_error_response('Question is required', 400)
        
        # Parse end_date
        try:
            end_date_dt = datetime.strptime(end_date, '%Y-%m-%d')
            end_date_timestamp = int(end_date_dt.timestamp())
        except ValueError:
            return standard_error_response('Invalid date format. Use YYYY-MM-DD', 400)
        
        # Create market in database first
        with db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO markets (question, description, category, end_date, created_by) 
                VALUES (?,?,?,?,?)
            ''', (question, description, data.get('category', ''), end_date, data.get('created_by', 'admin')))
            market_id = cursor.lastrowid
            cursor.execute('INSERT INTO market_state (market_id, q_yes, q_no) VALUES (?, 0.0, 0.0)', (market_id,))
        
        # Try blockchain transaction (currently placeholder)
        success, tx_hash, error = blockchain_service.create_market_on_chain(question, description, end_date_timestamp)
        
        if success and tx_hash:
            with db_transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE markets 
                    SET blockchain_tx_hash=?, contract_address=?
                    WHERE id=?
                ''', (tx_hash, Config.CONTRACT_ADDRESS, market_id))
        
        logger.info(f'Market {market_id} created with blockchain integration')
        
        return jsonify({
            'success': True,
            'market_id': market_id,
            'blockchain_tx_hash': tx_hash,
            'contract_address': Config.CONTRACT_ADDRESS,
            'etherscan_url': f'https://sepolia.etherscan.io/tx/{tx_hash}' if tx_hash and tx_hash.startswith('0x') else None,
            'blockchain_note': error if not success else None
        }), 201
        
    except Exception as e:
        logger.error(f'Create market blockchain error: {str(e)}')
        return standard_error_response('Failed to create market on blockchain', 500)

@api_bp.route('/markets/<int:market_id>/blockchain-status', methods=['GET'])
def get_blockchain_status(market_id):
    """Get blockchain verification status"""
    try:
        conn = get_db()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT blockchain_tx_hash, contract_address FROM markets WHERE id=?', (market_id,))
            row = cursor.fetchone()
            
            if not row or not row['blockchain_tx_hash']:
                return jsonify({
                    'on_blockchain': False,
                    'message': 'Market not deployed to blockchain'
                }), 200
            
            return jsonify({
                'on_blockchain': True,
                'tx_hash': row['blockchain_tx_hash'],
                'contract_address': row['contract_address'],
                'etherscan_tx_url': f'https://sepolia.etherscan.io/tx/{row["blockchain_tx_hash"]}',
                'etherscan_contract_url': f'https://sepolia.etherscan.io/address/{row["contract_address"]}' if row['contract_address'] else None
            }), 200
        finally:
            pass
    except Exception as e:
        logger.error(f'Get blockchain status error: {str(e)}')
        return standard_error_response('Failed to get blockchain status', 500)

# ========== CHATBOT API ==========
@api_bp.route('/chat', methods=['POST'])
def chat():
    """AI Chatbot endpoint with rate limiting (30 requests/minute)"""
    try:
        data = request.get_json() or {}
        message = data.get('message', '').strip()
        wallet = data.get('wallet', '').strip()
        thread_id = data.get('thread_id')
        
        if not message:
            return standard_error_response('Message is required', 400)
        
        # Lazy import to ensure env vars are loaded first
        from services.chatbot_service import get_chatbot_service
        chatbot_service = get_chatbot_service()
        if not chatbot_service.is_configured():
            return standard_error_response('Chatbot not configured', 500)
        
        response_text, thread_id, function_called = chatbot_service.chat(message, wallet, thread_id)
        
        return jsonify({
            'response': response_text,
            'thread_id': thread_id,
            'function_called': function_called
        }), 200
    
    except Exception as e:
        logger.error(f'Chat error: {str(e)}')
        return standard_error_response(f'Chat failed: {str(e)}', 500)

# ========== KYC API (Microservice Integration) ==========
@api_bp.route('/kyc/upload', methods=['POST'])
def upload_kyc_document():
    """Upload and verify identity document using KYC microservice"""
    try:
        data = request.get_json() or {}
        wallet = (data.get('wallet') or '').strip()
        document_image = (data.get('document_image') or '').strip()
        
        # Validate wallet address
        if not validate_wallet_address(wallet):
            return standard_error_response('Invalid wallet address', 400)
        
        # Validate image data presence
        if not document_image:
            return standard_error_response('Document image is required', 400)
        
        # Normalize wallet address to lowercase for consistent storage/lookup
        wallet = wallet.lower()
        
        # Check if already verified - allow re-verification but track if reward should be given
        conn = get_db()
        already_verified = False
        try:
            cursor = conn.cursor()
            # Use LOWER() for case-insensitive lookup
            cursor.execute('SELECT status FROM kyc_verifications WHERE LOWER(wallet)=?', (wallet,))
            existing = cursor.fetchone()
            
            if existing and existing['status'] == 'verified':
                already_verified = True
                logger.info(f'Re-verification attempt for already verified wallet {wallet[:10]}... (no reward will be given)')
        finally:
            pass
        
        # Call KYC microservice for verification
        from services.kyc_microservice import get_kyc_microservice
        kyc_microservice = get_kyc_microservice()
        
        if not kyc_microservice.is_configured():
            return standard_error_response('KYC service temporarily unavailable', 503)
        
        # Verify document using microservice
        result = kyc_microservice.verify_document(document_image)
        
        # Handle microservice errors
        if not result.get('success'):
            error_code = result.get('error_code', 'UNKNOWN_ERROR')
            error_message = result.get('error', 'Verification failed')
            
            # Map error codes to HTTP status codes
            status_code_map = {
                'INVALID_BASE64': 400,
                'INVALID_IMAGE': 400,
                'SERVICE_UNAVAILABLE': 503,
                'INTERNAL_ERROR': 500
            }
            
            status_code = status_code_map.get(error_code, 400)
            
            logger.warning(f'KYC microservice error for wallet {wallet[:10]}...: {error_code} - {error_message}')
            return standard_error_response(error_message, status_code)
        
        # Extract AI verification result
        ai_result = result.get('data', {})
        
        # Determine if verification successful
        # Strict criteria: must be official document with high confidence and all required fields
        is_verified = (
            ai_result.get('is_official_document', False) and
            ai_result.get('confidence') == 'high' and
            ai_result.get('full_name') and
            ai_result.get('date_of_birth') and
            ai_result.get('document_number') and
            ai_result.get('nationality')
        )
        
        # Update database with transaction safety
        with db_transaction() as conn:
            cursor = conn.cursor()
            
            if is_verified:
                # Insert or update KYC record as verified
                cursor.execute('''
                    INSERT INTO kyc_verifications (
                        wallet, status, full_name, date_of_birth, document_number,
                        nationality, document_type, is_official_document,
                        verification_notes, verified_at, updated_at
                    ) VALUES (?, 'verified', ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT(wallet) DO UPDATE SET
                        status='verified',
                        full_name=excluded.full_name,
                        date_of_birth=excluded.date_of_birth,
                        document_number=excluded.document_number,
                        nationality=excluded.nationality,
                        document_type=excluded.document_type,
                        is_official_document=excluded.is_official_document,
                        verification_notes=excluded.verification_notes,
                        verified_at=CURRENT_TIMESTAMP,
                        updated_at=CURRENT_TIMESTAMP
                ''', (
                    wallet,
                    ai_result.get('full_name', ''),
                    ai_result.get('date_of_birth', ''),
                    ai_result.get('document_number', ''),
                    ai_result.get('nationality', ''),
                    ai_result.get('document_type', ''),
                    1 if ai_result.get('is_official_document') else 0,
                    ai_result.get('verification_notes', '')
                ))
                
                # Credit user with KYC reward ONLY if not already verified
                reward_given = False
                if not already_verified:
                    update_user_balance(wallet, Config.KYC_REWARD_AMOUNT, 'add')
                    reward_given = True
                    logger.info(f'KYC verified for wallet {wallet[:10]}..., credited {Config.KYC_REWARD_AMOUNT} USDC')
                else:
                    logger.info(f'KYC re-verified for wallet {wallet[:10]}... (no reward - already verified previously)')
                
                return jsonify({
                    'status': 'verified',
                    'message': f'Identity verified!{" " + str(Config.KYC_REWARD_AMOUNT) + " USDC credited to your account." if reward_given else " (Re-verification - no reward given)"}',
                    'reward_given': reward_given,
                    'data': {
                        'full_name': ai_result.get('full_name', ''),
                        'date_of_birth': ai_result.get('date_of_birth', ''),
                        'document_number': ai_result.get('document_number', ''),
                        'nationality': ai_result.get('nationality', ''),
                        'document_type': ai_result.get('document_type', '')
                    }
                }), 200
            else:
                # Insert or update KYC record as rejected
                rejection_reason = ai_result.get('verification_notes', 'Document verification failed')
                
                # Provide user-friendly rejection reasons
                if not ai_result.get('is_official_document'):
                    rejection_reason = "Document does not appear to be an official government-issued ID. Please upload a passport, driver's license, or national ID card."
                elif ai_result.get('confidence') != 'high':
                    rejection_reason = "Image quality is too low or document text is not clearly visible. Please upload a clear, well-lit photo of your ID."
                
                cursor.execute('''
                    INSERT INTO kyc_verifications (
                        wallet, status, is_official_document, verification_notes, updated_at
                    ) VALUES (?, 'rejected', ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(wallet) DO UPDATE SET
                        status='rejected',
                        is_official_document=excluded.is_official_document,
                        verification_notes=excluded.verification_notes,
                        updated_at=CURRENT_TIMESTAMP
                ''', (
                    wallet,
                    1 if ai_result.get('is_official_document') else 0,
                    rejection_reason
                ))
                
                logger.warning(f'KYC rejected for wallet {wallet[:10]}...: {rejection_reason}')
                
                return jsonify({
                    'status': 'rejected',
                    'message': 'Verification failed. Please try again with a clear photo of your official ID.',
                    'reason': rejection_reason
                }), 200
    
    except Exception as e:
        logger.error(f'KYC upload error: {str(e)}', exc_info=True)
        return standard_error_response('KYC verification failed due to server error', 500)

@api_bp.route('/kyc/status', methods=['GET'])
def get_kyc_status():
    """Get KYC verification status for a wallet"""
    try:
        wallet = request.args.get('wallet', '').strip()
        
        if not validate_wallet_address(wallet):
            return standard_error_response('Invalid wallet address', 400)
        
        # Normalize wallet address to lowercase for consistent lookup
        wallet = wallet.lower()
        
        conn = get_db()
        try:
            cursor = conn.cursor()
            # Use LOWER() for case-insensitive lookup
            cursor.execute('''
                SELECT status, full_name, date_of_birth, document_number,
                       nationality, document_type, verification_notes,
                       verified_at, created_at, updated_at
                FROM kyc_verifications
                WHERE LOWER(wallet)=?
            ''', (wallet,))
            
            row = cursor.fetchone()
            
            if not row:
                return jsonify({
                    'status': 'not_submitted',
                    'message': 'No KYC submission found'
                }), 200
            
            kyc_data = dict(_row_to_dict(row))
            
            return jsonify({
                'status': kyc_data['status'],
                'data': kyc_data
            }), 200
        finally:
            pass
    
    except Exception as e:
        logger.error(f'KYC status error: {str(e)}')
        return standard_error_response(f'Failed to get KYC status: {str(e)}', 500)

__all__ = ['api_bp']

