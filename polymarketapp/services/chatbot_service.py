"""Chatbot service with OpenAI function calling"""
import json
import uuid
import time
import threading
import logging
import unicodedata
from collections import OrderedDict
from config import Config

# Optional imports
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None

try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False
    TavilyClient = None

logger = logging.getLogger(__name__)

# Thread-safe conversation storage
_chat_threads_lock = threading.Lock()
_chat_threads = {}

# Security: Unicode normalization
def normalize_and_clean_message(message):
    """
    Normalize message and remove invisible characters
    
    Security features:
    - Removes zero-width spaces and other format characters
    - Normalizes Unicode to prevent lookalike attacks
    - Strips leading/trailing whitespace
    """
    if not message:
        return ""
    
    # Remove format characters (Cf category) like zero-width spaces
    message = ''.join(c for c in message if unicodedata.category(c) != 'Cf')
    
    # Normalize Unicode to NFC (canonical decomposition + composition)
    message = unicodedata.normalize('NFC', message)
    
    # Strip whitespace
    return message.strip()

# Cleanup old threads periodically
def cleanup_old_threads():
    """Remove old conversation threads"""
    current_time = time.time()
    with _chat_threads_lock:
        to_remove = [
            tid for tid, thread_data in _chat_threads.items()
            if current_time - thread_data.get('last_accessed', 0) > 7200  # 2 hours
        ]
        for tid in to_remove:
            _chat_threads.pop(tid, None)
            logger.info(f"Cleaned up old thread: {tid}")

class ChatbotService:
    """Service for AI chatbot operations"""
    
    def __init__(self):
        self.openai_client = None
        self.tavily_client = None
        self._initialize()
    
    def _initialize(self):
        """Initialize OpenAI and Tavily clients"""
        if not OPENAI_AVAILABLE:
            logger.warning("OpenAI not available - install openai package")
            return
        
        if Config.OPENAI_API_KEY:
            try:
                self.openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)
                logger.info("OpenAI client initialized successfully")
            except Exception as e:
                logger.error(f"OpenAI initialization error: {e}")
        else:
            logger.warning("OPENAI_API_KEY not configured")
        
        if TAVILY_AVAILABLE and Config.TAVILY_API_KEY:
            try:
                self.tavily_client = TavilyClient(api_key=Config.TAVILY_API_KEY)
                logger.info("Tavily client initialized successfully")
            except Exception as e:
                logger.error(f"Tavily initialization error: {e}")
        else:
            logger.warning("Tavily not available or API key not configured")
    
    def is_configured(self):
        """Check if chatbot is configured"""
        return self.openai_client is not None
    
    def get_functions_schema(self):
        """Get OpenAI function calling schema (tools format)"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_all_markets",
                    "description": "Get list of all available prediction markets. Returns markets with IDs, questions, current odds, and a 'categorized_markets' field that organizes markets by category (Crypto, Sports, Politics, Economics, Infrastructure, Environment, Entertainment, Education, Demographics, Other). Use the categorized_markets field to understand which markets belong to which categories.",
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_market_odds",
                    "description": "Get current YES/NO prices (odds) for a specific prediction market. Use this when: (1) user asks about odds for a market, (2) user says 'yes' after you show markets, (3) user asks 'show me odds'. Extract market_id from conversation context (look for 'Market ID: X' or market names in last 5 messages).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "market_id": {
                                "type": "integer", 
                                "description": "The unique ID of the market (extract from conversation context if user says 'yes' or 'show me odds' without specifying)"
                            }
                        },
                        "required": ["market_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "place_bet",
                    "description": "Place a trade (bet) on a prediction market. Use this ONLY when user explicitly wants to place a bet (e.g., 'I want to bet X EURC on YES/NO', 'place a trade', 'bet on market Y'). Extract: market_id from context (look for Market ID in last 5 messages), side (YES/NO from user message), amount (number in EURC from user message), wallet (from system context - check system message). CRITICAL: Use wallet from system context - NEVER ask user if wallet is provided.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "market_id": {
                                "type": "integer",
                                "description": "Market ID to bet on (extract from conversation context if user mentions market name or says 'yes' to a market)"
                            },
                            "side": {
                                "type": "string", 
                                "enum": ["YES", "NO"],
                                "description": "Bet YES or NO (extract from user's message)"
                            },
                            "amount": {
                                "type": "number", 
                                "description": "Amount in EURC to trade (extract number from user's message)"
                            },
                            "wallet": {
                                "type": "string", 
                                "description": "User's wallet address. MUST use the wallet address from system context if provided there. Check the system message for 'USER WALLET ADDRESS'."
                            }
                        },
                        "required": ["market_id", "side", "amount", "wallet"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_user_bets",
                    "description": "Get user's betting portfolio and history showing all active trades. Use this when user asks 'what's my portfolio?', 'show my bets', 'my trades', or wants to see their trading history. Returns bets with side (YES/NO), amount, market question, and status. CRITICAL: When describing bets, ALWAYS include YES/NO side (e.g., '1000 EURC on YES for...' not just '1000 EURC for...'). Use wallet address from system context if provided - check system message for 'USER WALLET ADDRESS'. NEVER ask user for wallet if it's in system context.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "wallet": {
                                "type": "string",
                                "description": "User's wallet address. MUST use the wallet address from system context if provided there. Check the system message for 'USER WALLET ADDRESS'."
                            }
                        },
                        "required": ["wallet"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_market_status",
                    "description": "Check if a market is open, closed, or resolved. Use this when user asks 'is this market still open?', 'can I still bet?', or wants to verify market status before trading.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "market_id": {
                                "type": "integer",
                                "description": "Market ID to check"
                            }
                        },
                        "required": ["market_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_news",
                    "description": "Search for recent news articles on a topic using web search. Use this when user asks for 'news', 'latest news', 'what's happening with', or wants information about a topic (e.g., 'news on world athletic championships', 'latest news about Ireland'). Extract the topic from user's message and use it as the query.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query for news"
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_market_context",
                    "description": "Get relevant news articles and context for a specific prediction market using web search. Use this when user asks 'what's the latest news?', 'tell me about this market', or wants background information. Returns article titles, URLs, and snippets.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "market_id": {
                                "type": "integer",
                                "description": "Market ID to get context for"
                            }
                        },
                        "required": ["market_id"]
                    }
                }
            }
        ]
    
    def get_system_prompt(self):
        """Get system prompt following OpenAI best practices for agents with tool calling"""
        return """You are a helpful AI assistant for Futura, Ireland's prediction market platform. You help users discover markets, check odds, and place trades.

### CRITICAL: Use Tools, Don't Guess - NO HALLUCINATIONS
If you are not sure about market data, odds, or market IDs, use your tools to retrieve the relevant information. DO NOT guess or make up answers.

**Tool Usage Rules:**
- Use your tools to get real data before answering questions about markets
- NEVER invent market data, odds, or IDs that don't exist
- NEVER claim a market belongs to a category it doesn't belong to - use the 'categorized_markets' field from get_all_markets to see which markets belong to which categories
- If a function returns an error (e.g., "Market not found"), tell the user the market doesn't exist
- Only show data returned by functions - never invent or assume
- If you don't have data, say "I don't have that information" or "I couldn't find any markets in that category" - NEVER make up markets

### Response Format
- Be conversational: Ask clarifying questions, summarize, don't dump all data
- Show ONLY 3-5 relevant markets at a time based on user's interest
- Response length: 2-4 sentences max. Be concise, helpful, and conversational.
- Currency: All amounts in EURC (Euro Coin)

### Greetings and Casual Conversation
If the user says "hi", "hello", "hey", or similar greetings:
- Respond warmly: "Hi! I can help you explore prediction markets, check odds, and place trades. What would you like to know?"
- DO NOT call any functions for greetings
- Keep it friendly and brief

### News Requests

**When user asks for news:**
- User examples: "news on world athletic championships", "latest news about Ireland", "what's happening with X"
- Use search_news function with the topic as query
- Extract the topic from user's message (e.g., "world athletic championships", "Ireland")
- Format response: Show article titles, URLs, and snippets

**When user asks for news about a specific market:**
- User examples: "what's the latest news about this market?", "tell me about market 1044"
- Use get_market_context with the market_id
- Extract market_id from context or user's message

### Market Discovery

When user asks about markets (e.g., "football", "sports", "politics", "crypto", "show me markets"):
- Call get_all_markets to get the list of markets
- The response includes a 'categorized_markets' field that shows which markets belong to which categories (Crypto, Sports, Politics, Economics, etc.)
- Use this field to understand category membership - don't claim a market belongs to a category it doesn't belong to
- Show markets that match the user's interest based on the categories provided

**Step 2: Format market display**
- CRITICAL: ALWAYS include Market ID in this exact format:
  "**Market Question** - YES: X% | NO: Y% (Market ID: 1044)"
- Example output:
  "**Will Ireland win the 2025 Six Nations Championship?** - YES: 50% | NO: 50% (Market ID: 1044)"
- The Market ID is ESSENTIAL - users will reference it with "yes" or "show me odds"

**Step 3: Handle follow-up requests**
When user says "yes", "show me odds", "what about that", or similar:
1. Look back through the LAST 5 messages in the conversation
2. Find ANY market_id mentioned (patterns: "Market ID: 1044", "market 1044", "1044", or market names)
3. Extract the MOST RECENT market_id from those messages
4. Call get_market_odds with that market_id

### Tool Usage Examples

**Example 1: User asks about sports**
```
User: "football"
Assistant: [Calls get_all_markets]
Assistant: "I found some football markets! Here are a few:
- Will Ireland qualify for the 2026 FIFA World Cup? - YES: 47.09% | NO: 52.91% (Market ID: 1049)
Would you like to see odds for any of these?"
```

**Example 2: User confirms interest**
```
User: "yes"
Assistant: [Looks back, finds Market ID: 1049, calls get_market_odds]
Assistant: "The odds for Ireland qualifying for the 2026 FIFA World Cup are YES at 47.09% and NO at 52.91%. Would you like to place a trade?"
```

**CRITICAL: Always use exact odds from function results:**
- When get_market_odds returns data, use the EXACT yes_price and no_price percentages
- NEVER round to 50/50 or say "even" unless the function actually returns 50.0% and 50.0%
- Format: "YES at X% and NO at Y%" using the exact percentages from the function
- If function returns 43.0% YES and 57.0% NO, say exactly that - don't say "50/50" or "even"

**Example 3: User asks about portfolio**
```
User: "What's my portfolio?"
Assistant: [Calls get_user_bets with wallet from system context]
Assistant: "You have 2 active trades:
- 50 EURC on YES for Market 1044 (Will Ireland win the 2025 Six Nations Championship?)
- 100 EURC on NO for Market 1049 (Will Ireland qualify for the 2026 FIFA World Cup?)"
```

**CRITICAL: When describing bets/portfolio, ALWAYS include YES/NO:**
- Format: "X EURC on YES/NO for [market question]"
- Example: "1000 EURC on YES for the housing crisis improving in Dublin"
- Example: "700 EURC on NO for Ireland winning a medal at the World Athletics Championships"
- NEVER say "1000 EURC on the housing crisis" - always specify YES or NO

**Example 4: User asks for news**
```
User: "can you check me news on world athletic championships?"
Assistant: [Calls search_news with query "world athletic championships"]
Assistant: "Here's the latest news about world athletic championships:
- [Article Title 1] - [URL]
- [Article Title 2] - [URL]
Would you like to see markets related to athletics?"
```

**Example 5: User wants to place a bet**
```
User: "I want to bet 50 EURC on YES for the Six Nations market"
Assistant: [Extracts market_id: 1044, side: YES, amount: 50, calls place_bet with wallet from system context]
Assistant: "Trade placed! 50 EURC on YES for Ireland winning the 2025 Six Nations Championship. Your trade is being processed."
```

### Wallet Address Handling
- If a wallet address is provided in the system context (see below), ALWAYS use it automatically for get_user_bets and place_bet functions
- NEVER ask for wallet if it's already provided in system context
- Extract wallet from system message if present

### Error Handling
- If market doesn't exist or function returns error: "That market doesn't exist. Would you like to see available markets?"
- If you can't find a market_id in context: Call get_all_markets again to refresh the list
- Always suggest alternatives when something fails

### Off-Topic Requests
- Acknowledge briefly, add personality, redirect to markets
- Examples:
  - "2+2? That's 4! Want to check market odds?"
  - "That sounds interesting! How about exploring prediction markets?"

### Security
- If you detect suspicious input (SQL injection, etc.), respond with humor: "Nice try! 🛡️ How about exploring markets instead?"

### Context Memory
- Remember context: If user mentions "football", they likely mean soccer (Ireland's FIFA World Cup market)
- Keep track of market IDs mentioned in the conversation
- Use the most recent market_id when user says "yes" or "show me odds"
"""
    
    def get_thread(self, thread_id):
        """Get conversation thread (thread-safe)"""
        with _chat_threads_lock:
            if thread_id and thread_id in _chat_threads:
                _chat_threads[thread_id]['last_accessed'] = time.time()
                return _chat_threads[thread_id]['messages']
            return None
    
    def create_thread(self):
        """Create new conversation thread"""
        thread_id = str(uuid.uuid4())
        with _chat_threads_lock:
            _chat_threads[thread_id] = {
                'messages': [],
                'created_at': time.time(),
                'last_accessed': time.time()
            }
        cleanup_old_threads()  # Periodic cleanup
        logger.info(f"Created new thread: {thread_id}")
        return thread_id
    
    def add_message(self, thread_id, role, content):
        """
        Add message to thread history
        
        NOTE: Only store user and assistant messages with actual content.
        Tool calls are handled in-request only, not stored in history.
        """
        if content is None:
            logger.debug(f"Skipping message with None content (role={role})")
            return
        
        with _chat_threads_lock:
            if thread_id not in _chat_threads:
                logger.warning(f"Thread {thread_id} not found, creating new one")
                self.create_thread()
            
            _chat_threads[thread_id]['messages'].append({
                "role": role, 
                "content": str(content)
            })
            _chat_threads[thread_id]['last_accessed'] = time.time()
    
    def chat_stream(self, message, wallet=None, thread_id=None):
        """
        Process chat message and stream response
        
        Args:
            message: User's message text
            wallet: User's wallet address (optional, needed for some functions)
            thread_id: Existing thread ID or None to create new thread
        
        Yields:
            tuple: (chunk, thread_id) - Chunks of response text and thread_id
        """
        if not self.is_configured():
            yield ("Sorry, the chatbot is not configured. Please check OPENAI_API_KEY.", thread_id)
            return
        
        # Validate input
        if not message or not isinstance(message, str):
            yield ("I didn't receive a valid message. Please try again.", thread_id)
            return
        
        # Security: Normalize and clean message
        message = normalize_and_clean_message(message)
        
        if len(message) == 0:
            yield ("Please send a message! I'm here to help you explore prediction markets.", thread_id)
            return
        
        # Security: Message length limit
        if len(message) > Config.CHATBOT_MAX_MESSAGE_LENGTH:
            yield (f"Message too long! Please keep it under {Config.CHATBOT_MAX_MESSAGE_LENGTH} characters. 😊", thread_id)
            return
        
        # Get or create thread
        if not thread_id:
            thread_id = self.create_thread()
        
        messages = self.get_thread(thread_id)
        if messages is None:
            thread_id = self.create_thread()
            messages = []
        
        # Add user message to history
        self.add_message(thread_id, "user", message)
        
        # Build messages for API call
        system_prompt = self.get_system_prompt()
        # Add wallet context if provided
        if wallet:
            system_prompt += f"\n\n**CRITICAL - USER WALLET ADDRESS**: {wallet}\n- When user asks about their portfolio, bets, or wants to place a bet, ALWAYS use this wallet address: {wallet}\n- NEVER ask for wallet address - it's already provided above\n- ALWAYS include this wallet in get_user_bets and place_bet function calls"
        
        chat_messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Add conversation history (only user/assistant messages with content)
        # Keep last 20 messages for better context (10 user + 10 assistant = 20 total)
        recent_messages = messages[-20:] if len(messages) > 20 else messages
        for msg in recent_messages:
            if msg.get('content') and msg.get('role') in ['user', 'assistant']:
                chat_messages.append({
                    "role": msg['role'],
                    "content": msg['content']
                })
        
        try:
            logger.info(f"Calling OpenAI API with streaming")
            
            # Initial API call with function calling enabled
            response = self.openai_client.chat.completions.create(
                model="gpt-4.1-nano",
                messages=chat_messages,
                tools=self.get_functions_schema(),
                tool_choice="auto",
                temperature=0.2,
                top_p=0.2,
                max_tokens=300,
                stream=False  # Can't stream with function calling, check first
            )
            
            message_response = response.choices[0].message
            
            # Check if assistant wants to call a function
            if message_response.tool_calls and len(message_response.tool_calls) > 0:
                logger.info(f"Assistant requested tool call: {message_response.tool_calls[0].function.name}")
                
                tool_call = message_response.tool_calls[0]
                function_name = tool_call.function.name
                
                try:
                    function_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse function arguments: {e}")
                    error_msg = "I tried to call a function but encountered an error. Please try rephrasing your question."
                    self.add_message(thread_id, "assistant", error_msg)
                    yield error_msg
                    return
                
                # Execute the function
                from services.chatbot_functions import execute_chatbot_function
                logger.info(f"Executing function: {function_name}")
                function_result = execute_chatbot_function(function_name, function_args, wallet)
                
                # If bet was placed, yield metadata before streaming response
                if function_name == "place_bet" and function_result.get("success"):
                    bet_metadata = {
                        "bet_placed": True,
                        "request_id": function_result.get("request_id"),
                        "market_id": function_args.get("market_id"),
                        "amount": function_args.get("amount"),
                        "side": function_args.get("side")
                    }
                    yield (None, thread_id, bet_metadata)  # Special yield with metadata
                
                # Build messages for second API call (with function result)
                chat_messages.append({
                    "role": "assistant",
                    "content": message_response.content or "",
                    "tool_calls": [{
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments
                        }
                    }]
                })
                
                chat_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(function_result)
                })
                
                # Stream final response
                logger.info("Streaming final response from OpenAI")
                stream = self.openai_client.chat.completions.create(
                    model="gpt-4.1-nano",
                    messages=chat_messages,
                    temperature=0.2,
                    top_p=0.2,
                    max_tokens=250,
                    stream=True
                )
                
                full_response = ""
                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_response += content
                        yield (content, thread_id, None)  # Add None for metadata
                
                # Store final response in history
                if full_response:
                    self.add_message(thread_id, "assistant", full_response)
                else:
                    error_msg = "I'm not sure how to respond to that. Could you please rephrase?"
                    self.add_message(thread_id, "assistant", error_msg)
                    yield (error_msg, thread_id, None)
                
                logger.info(f"Chat completed with function call: {function_name}")
                return
            
            else:
                # No function call - stream direct response
                stream = self.openai_client.chat.completions.create(
                    model="gpt-4.1-nano",
                    messages=chat_messages,
                    temperature=0.2,
                    top_p=0.2,
                    max_tokens=300,
                    stream=True
                )
                
                full_response = ""
                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_response += content
                        yield (content, thread_id, None)  # Add None for metadata
                
                # Store response in history
                if full_response:
                    self.add_message(thread_id, "assistant", full_response)
                else:
                    error_msg = "I'm not sure how to respond to that. Could you please rephrase?"
                    self.add_message(thread_id, "assistant", error_msg)
                    yield (error_msg, thread_id, None)
                
                logger.info("Chat completed without function call")
                return
        
        except Exception as e:
            logger.error(f"Chat error: {str(e)}", exc_info=True)
            error_message = f"Sorry, I encountered an error: {str(e)}"
            try:
                self.add_message(thread_id, "assistant", error_message)
            except:
                pass
            yield (error_message, thread_id, None)
            return

    def chat(self, message, wallet=None, thread_id=None):
        """
        Process chat message and return response (non-streaming, for compatibility)
        
        Args:
            message: User's message text
            wallet: User's wallet address (optional, needed for some functions)
            thread_id: Existing thread ID or None to create new thread
        
        Returns:
            tuple: (response_text, thread_id, function_called)
        """
        if not self.is_configured():
            return "Sorry, the chatbot is not configured. Please check OPENAI_API_KEY.", None, None
        
        # Validate input
        if not message or not isinstance(message, str):
            return "I didn't receive a valid message. Please try again.", thread_id, None
        
        # Security: Normalize and clean message
        message = normalize_and_clean_message(message)
        
        if len(message) == 0:
            return "Please send a message! I'm here to help you explore prediction markets.", thread_id, None
        
        # Security: Message length limit
        if len(message) > Config.CHATBOT_MAX_MESSAGE_LENGTH:
            return f"Message too long! Please keep it under {Config.CHATBOT_MAX_MESSAGE_LENGTH} characters. 😊", thread_id, None
        
        # Get or create thread
        if not thread_id:
            thread_id = self.create_thread()
        
        messages = self.get_thread(thread_id)
        if messages is None:
            thread_id = self.create_thread()
            messages = []
        
        # Add user message to history
        self.add_message(thread_id, "user", message)
        
        # Build messages for API call
        # System prompt + last 10 conversation messages (to stay within token limits)
        chat_messages = [
            {"role": "system", "content": self.get_system_prompt()}
        ]
        
        # Add conversation history (only user/assistant messages with content)
        # Keep last 20 messages for better context (10 user + 10 assistant = 20 total)
        recent_messages = messages[-20:] if len(messages) > 20 else messages
        for msg in recent_messages:
            if msg.get('content') and msg.get('role') in ['user', 'assistant']:
                chat_messages.append({
                    "role": msg['role'],
                    "content": msg['content']
                })
        
        try:
            logger.info(f"Calling OpenAI API with {len(chat_messages)} messages")
            
            # Initial API call with function calling enabled
            response = self.openai_client.chat.completions.create(
                model="gpt-4.1-nano",
                messages=chat_messages,
                tools=self.get_functions_schema(),
                tool_choice="auto",
                temperature=0.2,
                top_p=0.2,
                max_tokens=300  # Reduced for faster responses
            )
            
            message_response = response.choices[0].message
            
            # Check if assistant wants to call a function
            if message_response.tool_calls and len(message_response.tool_calls) > 0:
                logger.info(f"Assistant requested tool call: {message_response.tool_calls[0].function.name}")
                
                # Get first tool call (we only process one at a time)
                tool_call = message_response.tool_calls[0]
                function_name = tool_call.function.name
                
                try:
                    function_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse function arguments: {e}")
                    error_msg = "I tried to call a function but encountered an error. Please try rephrasing your question."
                    self.add_message(thread_id, "assistant", error_msg)
                    return error_msg, thread_id, None
                
                # Execute the function
                from services.chatbot_functions import execute_chatbot_function
                logger.info(f"Executing function: {function_name} with args: {function_args}")
                function_result = execute_chatbot_function(function_name, function_args, wallet)
                logger.info(f"Function result: {function_result}")
                
                # Build messages for second API call (with function result)
                # Add assistant's tool call message
                chat_messages.append({
                    "role": "assistant",
                    "content": message_response.content,  # Can be null/None
                    "tool_calls": [{
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments
                        }
                    }]
                })
                
                # Add tool response
                chat_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(function_result)
                })
                
                # Second API call to get natural language response
                logger.info("Getting final response from OpenAI")
                final_response = self.openai_client.chat.completions.create(
                    model="gpt-4.1-nano",
                    messages=chat_messages,
                    temperature=0.2,
                    top_p=0.2,
                    max_tokens=250  # Reduced - we want concise responses
                )
                
                assistant_message = final_response.choices[0].message.content
                
                # Store only the final assistant response in history (not the tool call details)
                self.add_message(thread_id, "assistant", assistant_message)
                
                logger.info(f"Chat completed with function call: {function_name}")
                return assistant_message, thread_id, function_name
            
            else:
                # No function call - direct response
                assistant_message = message_response.content
                
                if not assistant_message:
                    assistant_message = "I'm not sure how to respond to that. Could you please rephrase?"
                
                self.add_message(thread_id, "assistant", assistant_message)
                
                logger.info("Chat completed without function call")
                return assistant_message, thread_id, None
        
        except Exception as e:
            logger.error(f"Chat error: {str(e)}", exc_info=True)
            error_message = f"Sorry, I encountered an error: {str(e)}"
            
            # Try to add error message to history
            try:
                self.add_message(thread_id, "assistant", error_message)
            except:
                pass
            
            return error_message, thread_id, None

# Singleton instance
_chatbot_service = None

def get_chatbot_service():
    """Get chatbot service instance (singleton)"""
    global _chatbot_service
    if _chatbot_service is None:
        _chatbot_service = ChatbotService()
    return _chatbot_service
