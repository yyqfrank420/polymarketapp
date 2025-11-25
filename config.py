"""Configuration management - NO hardcoded secrets"""
import os

class Config:
    """Application configuration"""
    
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY')
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
    DEBUG = FLASK_ENV == 'development'
    
    # Database
    DATABASE_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'polymarket.db')
    
    # Blockchain (require env vars)
    INFURA_PROJECT_ID = os.environ.get('INFURA_PROJECT_ID')
    SEPOLIA_RPC_URL = os.environ.get('SEPOLIA_RPC_URL')
    CONTRACT_ADDRESS = os.environ.get('CONTRACT_ADDRESS', '')
    PRIVATE_KEY = os.environ.get('PRIVATE_KEY', '')  # For signing transactions
    
    # OpenAI (require env var)
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    
    # Tavily News API (require env var)
    TAVILY_API_KEY = os.environ.get('TAVILY_API_KEY')
    
    # LMSR Configuration
    # LMSR_B should be proportional to total liquidity to prevent excessive price swings
    # With buffer of 10000 on each side, b should be ~5000-10000 for reasonable liquidity
    LMSR_B = 5000.0  # Liquidity parameter (increased from 100 to prevent 99/1 swings on 2000 EURC bets)
    LMSR_BUFFER = 10000.0  # Initial buffer ($10k on each side to prevent early swings)
    
    # User Balance
    INITIAL_FAKE_CRYPTO_BALANCE = 1000.0
    
    # Fee Structure (like Polymarket)
    PROFIT_FEE_RATE = 0.02  # 2% fee on net profits from winning trades
    
    # Bet Queue Configuration
    BET_RESULT_TTL = 3600  # 1 hour
    MAX_BET_RESULTS = 1000
    
    # Security Configuration
    CHATBOT_RATE_LIMIT = "30 per minute"  # 30 requests/min per IP
    CHATBOT_MAX_MESSAGE_LENGTH = 1000  # Maximum characters in a message
    
    # KYC Configuration
    KYC_REWARD_AMOUNT = 20.0  # EURC reward for verification
    KYC_MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB max image size
    KYC_RATE_LIMIT = "5 per hour"  # Per wallet address
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        required = [
            ('OPENAI_API_KEY', cls.OPENAI_API_KEY),
            ('TAVILY_API_KEY', cls.TAVILY_API_KEY),
        ]
        
        missing = [name for name, value in required if not value]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        
        return True

