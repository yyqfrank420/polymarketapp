"""Blockchain service - Sepolia testnet integration"""
import logging
from config import Config

# Optional imports
try:
    from web3 import Web3
    from eth_account import Account
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False
    Web3 = None
    Account = None

logger = logging.getLogger(__name__)

class BlockchainService:
    """Service for blockchain operations"""
    
    def __init__(self):
        self.w3 = None
        self.contract = None
        self.account = None
        self._initialize()
    
    def _initialize(self):
        """Initialize Web3 connection and contract"""
        if not WEB3_AVAILABLE:
            logger.warning("Web3 not available - install web3 package")
            return
        
        if not Config.SEPOLIA_RPC_URL:
            logger.warning("Blockchain not configured - SEPOLIA_RPC_URL missing")
            return
        
        try:
            self.w3 = Web3(Web3.HTTPProvider(Config.SEPOLIA_RPC_URL))
            
            if not self.w3.is_connected():
                logger.warning("Failed to connect to Sepolia RPC")
                return
            
            # Load contract if address provided
            if Config.CONTRACT_ADDRESS:
                # In production, load ABI from artifacts
                # For now, we'll use minimal interaction
                self.contract_address = Web3.to_checksum_address(Config.CONTRACT_ADDRESS)
            
            # Initialize account if private key provided
            if Config.PRIVATE_KEY:
                self.account = Account.from_key(Config.PRIVATE_KEY)
                logger.info(f"Blockchain account initialized: {self.account.address}")
            
        except Exception as e:
            logger.error(f"Blockchain initialization error: {e}")
    
    def is_configured(self):
        """Check if blockchain is properly configured"""
        return self.w3 is not None and self.w3.is_connected() and Config.CONTRACT_ADDRESS
    
    def create_market_on_chain(self, question, description, end_date_timestamp):
        """
        Create market on blockchain
        
        Returns: (success, tx_hash, error_message)
        """
        if not self.is_configured():
            return False, None, "Blockchain not configured"
        
        if not self.account:
            return False, None, "Private key not configured for transactions"
        
        try:
            # TODO: Load contract ABI and call createMarket()
            # For now, return placeholder
            # In production, this would:
            # 1. Load contract ABI
            # 2. Build transaction
            # 3. Sign with account
            # 4. Send transaction
            # 5. Return real tx_hash
            
            logger.warning("Blockchain transaction not fully implemented - using placeholder")
            return False, None, "Blockchain transactions require contract ABI deployment"
            
        except Exception as e:
            logger.error(f"Blockchain transaction error: {e}")
            return False, None, str(e)
    
    def resolve_market_on_chain(self, market_id, resolution):
        """Resolve market on blockchain"""
        if not self.is_configured():
            return False, None, "Blockchain not configured"
        
        # Similar to create_market_on_chain
        return False, None, "Not implemented"

    def get_market_from_chain(self, market_id):
        """Get market data from blockchain"""
        if not self.is_configured():
            return None
        
        # TODO: Call contract.getMarket(market_id)
        return None

# Singleton instance
_blockchain_service = None

def get_blockchain_service():
    """Get blockchain service instance (singleton)"""
    global _blockchain_service
    if _blockchain_service is None:
        _blockchain_service = BlockchainService()
    return _blockchain_service

