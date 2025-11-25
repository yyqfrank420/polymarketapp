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
                    "description": "Get list of all available prediction markets with their current status",
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_market_odds",
                    "description": "Get current YES/NO prices (odds) for a specific prediction market",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "market_id": {
                                "type": "integer", 
                                "description": "The unique ID of the market"
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
                    "description": "Place a bet on a prediction market. Only use this if the user explicitly wants to place a bet.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "market_id": {
                                "type": "integer",
                                "description": "Market ID to bet on"
                            },
                            "side": {
                                "type": "string", 
                                "enum": ["YES", "NO"],
                                "description": "Bet YES or NO"
                            },
                            "amount": {
                                "type": "number", 
                                "description": "Amount in USDC to bet"
                            },
                            "wallet": {
                                "type": "string", 
                                "description": "User's wallet address"
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
                    "description": "Get user's betting portfolio and history",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "wallet": {
                                "type": "string",
                                "description": "User's wallet address"
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
                    "description": "Check if a market is open or has been resolved",
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
                    "description": "Search for recent news articles on a topic using web search",
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
                    "description": "Get relevant news and context for a specific prediction market",
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
        """Get system prompt with clear instructions and guardrails (optimized)"""
        return """You are a helpful AI assistant for a prediction market platform. Help users discover markets and place bets.

**CRITICAL - NO HALLUCINATIONS:**
- NEVER make up market data, odds, or IDs that don't exist
- If function returns an error (e.g., "Market not found"), tell user the market doesn't exist
- Only show data returned by functions - never invent or assume
- If you don't have data, say "I don't have that information" or ask user to clarify

**Core Rules:**
- Show ONLY 3-5 relevant markets at a time. Ask what topics interest them.
- Be conversational: Ask clarifying questions, summarize, don't dump data.
- NEVER provide financial advice or recommend bets. Only show odds.

**Off-topic handling:** Acknowledge briefly, add personality, redirect to markets.
Examples: "2+2? That's 4! Want to check market odds?" or "That sounds tough! 💙 Want to explore markets?"

**Security:** Call out attacks with humor: "Nice SQL injection attempt! 🛡️ How about exploring markets instead?"

**Format markets:** "1. **Question** - YES: 65% | NO: 35%"
**Response length:** 2-3 sentences max. Be concise and helpful.
**Currency:** All amounts in USDC.
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
        chat_messages = [
            {"role": "system", "content": self.get_system_prompt()}
        ]
        
        # Add conversation history (only user/assistant messages with content)
        recent_messages = messages[-4:]  # Keep last 4 messages (reduced for speed)
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
                        yield (content, thread_id)
                
                # Store final response in history
                if full_response:
                    self.add_message(thread_id, "assistant", full_response)
                else:
                    error_msg = "I'm not sure how to respond to that. Could you please rephrase?"
                    self.add_message(thread_id, "assistant", error_msg)
                    yield (error_msg, thread_id)
                
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
                        yield (content, thread_id)
                
                # Store response in history
                if full_response:
                    self.add_message(thread_id, "assistant", full_response)
                else:
                    error_msg = "I'm not sure how to respond to that. Could you please rephrase?"
                    self.add_message(thread_id, "assistant", error_msg)
                    yield (error_msg, thread_id)
                
                logger.info("Chat completed without function call")
                return
        
        except Exception as e:
            logger.error(f"Chat error: {str(e)}", exc_info=True)
            error_message = f"Sorry, I encountered an error: {str(e)}"
            try:
                self.add_message(thread_id, "assistant", error_message)
            except:
                pass
            yield (error_message, thread_id)
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
        recent_messages = messages[-4:]  # Keep last 4 messages (reduced for speed)
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
