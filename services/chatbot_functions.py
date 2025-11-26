"""Chatbot tool call implementations - called by chatbot service"""
import logging
import threading
from utils.database import get_db, _row_to_dict
from services.market_service import calculate_market_price
from services.bet_service import queue_bet
from services.user_service import get_user_balance
from services.chatbot_service import get_chatbot_service
from utils.validators import validate_amount, validate_side
from utils.cache import get_cache

logger = logging.getLogger(__name__)
_cache = get_cache()

def execute_chatbot_function(function_name, arguments_dict, wallet=None):
    """Execute chatbot function calls"""
    try:
        if function_name == "get_all_markets":
            # Check cache first (60 second TTL)
            cache_key = "all_markets"
            cached = _cache.get(cache_key, ttl=60)
            if cached:
                logger.info("Returning cached market list")
                return cached
            
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
                    
                    # Add current odds for open markets (with caching)
                    cache_key_odds = f"market_odds_{market['id']}"
                    cached_odds = _cache.get(cache_key_odds, ttl=30)
                    if cached_odds:
                        market['yes_odds'] = cached_odds['yes']
                        market['no_odds'] = cached_odds['no']
                    else:
                        try:
                            yes_price, no_price = calculate_market_price(market['id'])
                            yes_odds = round(yes_price * 100, 2)
                            no_odds = round(no_price * 100, 2)
                            market['yes_odds'] = yes_odds
                            market['no_odds'] = no_odds
                            _cache.set(cache_key_odds, {'yes': yes_odds, 'no': no_odds})
                        except:
                            market['yes_odds'] = None
                            market['no_odds'] = None
                    
                    # Categorize markets by keywords for AI to use (Ireland-focused)
                    question_lower = market['question'].lower()
                    if 'crypto' in question_lower or 'bitcoin' in question_lower or 'ethereum' in question_lower or 'blockchain' in question_lower or 'btc' in question_lower or 'eth' in question_lower or 'defi' in question_lower or 'nft' in question_lower or 'cryptocurrency' in question_lower:
                        categories.setdefault('Crypto', []).append(market)
                    elif 'sport' in question_lower or 'championship' in question_lower or 'six nations' in question_lower or 'fifa' in question_lower or 'world cup' in question_lower or 'ryder cup' in question_lower or 'athletics' in question_lower or 'eurovision' in question_lower:
                        categories.setdefault('Sports', []).append(market)
                    elif 'politic' in question_lower or 'election' in question_lower or 'government' in question_lower or 'dáil' in question_lower:
                        categories.setdefault('Politics', []).append(market)
                    elif 'econom' in question_lower or 'housing' in question_lower or 'price' in question_lower or 'gdp' in question_lower:
                        categories.setdefault('Economics', []).append(market)
                    elif 'dublin' in question_lower or 'metro' in question_lower or 'infrastructure' in question_lower:
                        categories.setdefault('Infrastructure', []).append(market)
                    elif 'renewable' in question_lower or 'climate' in question_lower or 'environment' in question_lower:
                        categories.setdefault('Environment', []).append(market)
                    elif 'entertainment' in question_lower or 'music' in question_lower or 'festival' in question_lower:
                        categories.setdefault('Entertainment', []).append(market)
                    elif 'education' in question_lower or 'language' in question_lower or 'leaving cert' in question_lower:
                        categories.setdefault('Education', []).append(market)
                    elif 'population' in question_lower or 'demographic' in question_lower:
                        categories.setdefault('Demographics', []).append(market)
                    else:
                        categories.setdefault('Other', []).append(market)
                    
                    markets.append(market)
                
                result = {
                    "markets": markets,
                    "count": len(markets),
                    "categories": {k: len(v) for k, v in categories.items()},
                    "categorized_markets": {k: [{"id": m["id"], "question": m["question"], "yes_odds": m.get("yes_odds"), "no_odds": m.get("no_odds")} for m in v] for k, v in categories.items()},
                    "message": f"Found {len(markets)} open markets across {len(categories)} categories: {', '.join(categories.keys())}. CRITICAL: When user asks for a specific category (e.g., 'crypto', 'sports', 'politics'), ONLY show markets from that category. Use the 'categorized_markets' field to filter. NEVER claim a market belongs to a category it doesn't belong to. When showing markets to users, ALWAYS include the Market ID in parentheses like '(Market ID: 1044)' so you can reference it later if they say 'yes' or 'show me odds'."
                }
                
                # Cache the result
                _cache.set(cache_key, result)
                return result
            finally:
                pass  # Connection managed by Flask
        
        elif function_name == "get_market_odds":
            market_id = arguments_dict.get('market_id')
            if not isinstance(market_id, int) or market_id <= 0:
                return {"error": "Invalid market_id"}
            
            # Check cache first (5 second TTL - short to ensure fresh odds after bets)
            cache_key = f"market_odds_{market_id}"
            cached = _cache.get(cache_key, ttl=5)
            if cached:
                logger.info(f"Returning cached odds for market {market_id}")
                return cached
            
            try:
                yes_price, no_price = calculate_market_price(market_id)
                result = {
                    "market_id": market_id,
                    "yes_price": round(yes_price * 100, 2),
                    "no_price": round(no_price * 100, 2),
                    "yes_price_cents": f"{round(yes_price * 100, 2)}¢",
                    "no_price_cents": f"{round(no_price * 100, 2)}¢"
                }
                _cache.set(cache_key, result)
                return result
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
                return {"error": "Amount must be positive and less than €1,000,000"}
            
            # Queue bet (returns tuple: request_id, queue_position)
            request_id, queue_position = queue_bet(market_id, wallet, side, amount)
            
            # Ensure worker is running
            from services.bet_service import ensure_worker_running
            ensure_worker_running()
            
            return {
                "success": True,
                "message": f"Trade queued: €{float(amount):.2f} on {side}",
                "request_id": request_id,
                "queue_position": queue_position,
                "status": "processing" if queue_position == 0 else "queued"
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
                    WHERE LOWER(b.wallet) = LOWER(?)
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
            
            # Check cache first (10 minute TTL - aggressive caching to avoid API calls)
            cache_key = f"news_{query.lower().strip()}"
            cached = _cache.get(cache_key, ttl=600)  # 10 minutes
            if cached:
                logger.info(f"Returning cached news for query: {query}")
                return cached
            
            chatbot_service = get_chatbot_service()
            if not chatbot_service.tavily_client:
                return {"error": "News search not configured"}
            
            # Only call Tavily if cache miss - synchronous call, then cache result
            try:
                logger.info(f"Calling Tavily API for query: {query}")
                response = chatbot_service.tavily_client.search(query, max_results=5)
                articles = []
                for result in response.get('results', []):
                    articles.append({
                        "title": result.get('title', ''),
                        "url": result.get('url', ''),
                        "content": result.get('content', '')[:200] + "..."
                    })
                result = {"articles": articles, "query": query}
                # Cache for 10 minutes to avoid repeated calls
                _cache.set(cache_key, result)
                logger.info(f"Cached news results for query: {query}")
                return result
            except Exception as e:
                logger.error(f'News search error: {str(e)}')
                return {"error": f"Failed to search news: {str(e)}"}
        
        elif function_name == "get_market_context":
            market_id = arguments_dict.get('market_id')
            if not isinstance(market_id, int) or market_id <= 0:
                return {"error": "Invalid market_id"}
            
            # Check cache first (10 minute TTL - aggressive caching)
            cache_key = f"market_context_{market_id}"
            cached = _cache.get(cache_key, ttl=600)  # 10 minutes
            if cached:
                logger.info(f"Returning cached context for market {market_id}")
                return cached
            
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
                
                # Only call Tavily if cache miss - synchronous call, then cache result
                try:
                    logger.info(f"Calling Tavily API for market context: {market_id}")
                    response = chatbot_service.tavily_client.search(query, max_results=3)
                    articles = []
                    for result in response.get('results', []):
                        articles.append({
                            "title": result.get('title', ''),
                            "url": result.get('url', ''),
                            "snippet": result.get('content', '')[:150] + "..."
                        })
                    result = {"market_id": market_id, "question": query, "articles": articles}
                    # Cache for 10 minutes
                    _cache.set(cache_key, result)
                    logger.info(f"Cached market context for market {market_id}")
                    return result
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

