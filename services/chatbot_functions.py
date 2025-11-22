"""Chatbot function implementations - called by chatbot service"""
import logging
from utils.database import get_db, _row_to_dict
from services.market_service import calculate_market_price
from services.bet_service import queue_bet
from services.user_service import get_user_balance
from services.chatbot_service import get_chatbot_service
from utils.validators import validate_amount, validate_side

logger = logging.getLogger(__name__)

def execute_chatbot_function(function_name, arguments_dict, wallet=None):
    """Execute chatbot function calls"""
    try:
        if function_name == "get_all_markets":
            conn = get_db()
            try:
                cursor = conn.cursor()
                # Get all markets, but prepare summary stats to help AI be intelligent
                cursor.execute('SELECT id, question, status, resolution FROM markets WHERE status="open" ORDER BY created_at DESC')
                raw_markets = cursor.fetchall()
                
                markets = []
                categories = {}  # Track categories for intelligent grouping
                
                for row in raw_markets:
                    market = dict(_row_to_dict(row))
                    
                    # Add current odds for open markets
                    try:
                        yes_price, no_price = calculate_market_price(market['id'])
                        market['yes_odds'] = round(yes_price * 100, 2)
                        market['no_odds'] = round(no_price * 100, 2)
                    except:
                        market['yes_odds'] = None
                        market['no_odds'] = None
                    
                    # Categorize markets by keywords for AI to use
                    question_lower = market['question'].lower()
                    if 'crypto' in question_lower or 'blockchain' in question_lower:
                        categories.setdefault('Cryptocurrency', []).append(market)
                    elif 'ie' in question_lower or 'university' in question_lower or 'school' in question_lower:
                        categories.setdefault('IE University', []).append(market)
                    elif 'sport' in question_lower or 'championship' in question_lower:
                        categories.setdefault('Sports', []).append(market)
                    elif 'politic' in question_lower or 'election' in question_lower:
                        categories.setdefault('Politics', []).append(market)
                    else:
                        categories.setdefault('Other', []).append(market)
                    
                    markets.append(market)
                
                return {
                    "markets": markets,
                    "count": len(markets),
                    "categories": {k: len(v) for k, v in categories.items()},
                    "message": f"Found {len(markets)} open markets across {len(categories)} categories. Be selective and ask user what they're interested in rather than showing all."
                }
            finally:
                pass  # Connection managed by Flask
        
        elif function_name == "get_market_odds":
            market_id = arguments_dict.get('market_id')
            if not isinstance(market_id, int) or market_id <= 0:
                return {"error": "Invalid market_id"}
            
            try:
                yes_price, no_price = calculate_market_price(market_id)
                return {
                    "market_id": market_id,
                    "yes_price": round(yes_price * 100, 2),
                    "no_price": round(no_price * 100, 2),
                    "yes_price_cents": f"{round(yes_price * 100, 2)}¢",
                    "no_price_cents": f"{round(no_price * 100, 2)}¢"
                }
            except ValueError as e:
                return {"error": str(e)}
        
        elif function_name == "place_bet":
            try:
                market_id = int(arguments_dict.get('market_id'))
                amount = float(arguments_dict.get('amount'))
            except (ValueError, TypeError):
                return {"error": "Invalid market_id or amount format"}

            side = arguments_dict.get('side')
            wallet = arguments_dict.get('wallet') or wallet
            
            # Validate inputs
            if not wallet:
                return {"error": "Wallet address required"}
            if market_id <= 0:
                return {"error": "Invalid market_id"}
            if not validate_side(side):
                return {"error": "Side must be YES or NO"}
            if not validate_amount(amount):
                return {"error": "Amount must be positive and less than $1,000,000"}
            
            # Queue bet
            request_id = queue_bet(market_id, wallet, side, amount)
            
            return {
                "success": True,
                "message": f"Bet queued: ${float(amount):.2f} on {side}",
                "request_id": request_id,
                "status": "processing"
            }
        
        elif function_name == "get_user_bets":
            wallet = arguments_dict.get('wallet') or wallet
            if not wallet:
                return {"error": "Wallet address required"}
            
            conn = get_db()
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT b.id, b.market_id, b.side, b.amount, b.shares, b.price_per_share, b.created_at,
                           m.question, m.status, m.resolution
                    FROM bets b
                    JOIN markets m ON b.market_id = m.id
                    WHERE b.wallet = ?
                    ORDER BY b.created_at DESC
                ''', (wallet,))
                
                bets = []
                for row in cursor.fetchall():
                    bet_info = dict(_row_to_dict(row))
                    if bet_info['status'] == 'resolved':
                        if bet_info['side'] == bet_info['resolution']:
                            bet_info['result'] = 'won'
                            bet_info['payout'] = bet_info['shares'] * 1.0
                        else:
                            bet_info['result'] = 'lost'
                            bet_info['payout'] = 0
                    else:
                        bet_info['result'] = 'pending'
                    bets.append(bet_info)
                
                return {"bets": bets, "count": len(bets)}
            finally:
                pass
        
        elif function_name == "check_market_status":
            market_id = arguments_dict.get('market_id')
            if not isinstance(market_id, int) or market_id <= 0:
                return {"error": "Invalid market_id"}
            
            conn = get_db()
            try:
                cursor = conn.cursor()
                cursor.execute('SELECT status, resolution FROM markets WHERE id=?', (market_id,))
                row = cursor.fetchone()
                
                if not row:
                    return {"error": "Market not found"}
                
                return {
                    "market_id": market_id,
                    "status": row['status'],
                    "resolution": row['resolution'],
                    "is_resolved": row['status'] == 'resolved'
                }
            finally:
                pass
        
        elif function_name == "search_news":
            query = arguments_dict.get('query')
            if not query:
                return {"error": "Query is required"}
            
            chatbot_service = get_chatbot_service()
            if not chatbot_service.tavily_client:
                return {"error": "News search not configured"}
            
            try:
                response = chatbot_service.tavily_client.search(query, max_results=5)
                articles = []
                for result in response.get('results', []):
                    articles.append({
                        "title": result.get('title', ''),
                        "url": result.get('url', ''),
                        "content": result.get('content', '')[:200] + "..."
                    })
                return {"articles": articles, "query": query}
            except Exception as e:
                logger.error(f'News search error: {str(e)}')
                return {"error": f"Failed to search news: {str(e)}"}
        
        elif function_name == "get_market_context":
            market_id = arguments_dict.get('market_id')
            if not isinstance(market_id, int) or market_id <= 0:
                return {"error": "Invalid market_id"}
            
            conn = get_db()
            try:
                cursor = conn.cursor()
                cursor.execute('SELECT question FROM markets WHERE id=?', (market_id,))
                row = cursor.fetchone()
                
                if not row:
                    return {"error": "Market not found"}
                
                query = row['question']
                chatbot_service = get_chatbot_service()
                if not chatbot_service.tavily_client:
                    return {"error": "News search not configured"}
                
                try:
                    response = chatbot_service.tavily_client.search(query, max_results=3)
                    articles = []
                    for result in response.get('results', []):
                        articles.append({
                            "title": result.get('title', ''),
                            "url": result.get('url', ''),
                            "snippet": result.get('content', '')[:150] + "..."
                        })
                    return {"market_id": market_id, "question": query, "articles": articles}
                except Exception as e:
                    logger.error(f'Market context search error: {str(e)}')
                    return {"error": f"Failed to get market context: {str(e)}"}
            finally:
                pass
        
        else:
            return {"error": f"Unknown function: {function_name}"}
    
    except Exception as e:
        logger.error(f'Function execution error: {str(e)}')
        return {"error": f"Failed to execute {function_name}: {str(e)}"}

