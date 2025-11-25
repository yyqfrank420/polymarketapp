"""Blockchain service - Sepolia testnet integration"""
import logging
from config import Config

# Optional imports
try:
    from web3 import Web3
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False
    Web3 = None

try:
    from eth_account import Account
    ETH_ACCOUNT_AVAILABLE = True
except ImportError:
    ETH_ACCOUNT_AVAILABLE = False
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
                if not ETH_ACCOUNT_AVAILABLE:
                    logger.warning("eth_account not available - install with: pip install eth-account")
                else:
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
            missing = []
            if not Config.SEPOLIA_RPC_URL:
                missing.append("SEPOLIA_RPC_URL")
            if not Config.CONTRACT_ADDRESS:
                missing.append("CONTRACT_ADDRESS")
            return False, None, f"Blockchain not configured. Missing: {', '.join(missing)}"
        
        if not self.account:
            return False, None, "Private key not configured for transactions"
        
        try:
            import json
            import os
            
            # Try to load contract ABI from artifacts
            artifacts_path = os.path.join(os.path.dirname(__file__), '..', 'artifacts', 'contracts', 'PredictionMarket.sol', 'PredictionMarket.json')
            
            if not os.path.exists(artifacts_path):
                # Try alternative path
                artifacts_path = os.path.join(os.path.dirname(__file__), '..', '..', 'artifacts', 'contracts', 'PredictionMarket.sol', 'PredictionMarket.json')
            
            if os.path.exists(artifacts_path):
                with open(artifacts_path, 'r') as f:
                    contract_data = json.load(f)
                    abi = contract_data.get('abi', [])
            else:
                # Use minimal ABI for createMarket function
                abi = [{
                    "inputs": [
                        {"internalType": "string", "name": "_question", "type": "string"},
                        {"internalType": "string", "name": "_description", "type": "string"},
                        {"internalType": "uint256", "name": "_endDate", "type": "uint256"}
                    ],
                    "name": "createMarket",
                    "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                    "stateMutability": "nonpayable",
                    "type": "function"
                }]
                logger.info("Using minimal ABI - compile contract for full ABI")
            
            # Create contract instance
            contract = self.w3.eth.contract(address=self.contract_address, abi=abi)
            
            # Build transaction
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            
            # Estimate gas
            try:
                gas_estimate = contract.functions.createMarket(
                    question,
                    description,
                    end_date_timestamp
                ).estimate_gas({'from': self.account.address})
                gas_limit = int(gas_estimate * 1.2)  # Add 20% buffer
            except Exception as gas_error:
                logger.warning(f"Gas estimation failed: {gas_error}, using default")
                gas_limit = 500000  # Default gas limit
            
            # Build transaction
            transaction = contract.functions.createMarket(
                question,
                description,
                end_date_timestamp
            ).build_transaction({
                'from': self.account.address,
                'nonce': nonce,
                'gas': gas_limit,
                'gasPrice': self.w3.eth.gas_price,
                'chainId': 11155111  # Sepolia chain ID
            })
            
            # Sign transaction
            if not ETH_ACCOUNT_AVAILABLE:
                return False, None, "eth_account package required for signing transactions. Install with: pip install eth-account"
            
            signed_txn = self.account.sign_transaction(transaction)
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Wait for transaction receipt (optional - can be async)
            logger.info(f"Transaction sent: {tx_hash.hex()}")
            
            return True, tx_hash.hex(), None
            
        except FileNotFoundError:
            logger.error("Contract ABI not found. Please compile the contract first: npm run compile")
            return False, None, "Contract ABI not found. Run 'npm run compile' to generate ABI"
        except Exception as e:
            logger.error(f"Blockchain transaction error: {e}", exc_info=True)
            return False, None, f"Transaction failed: {str(e)}"
    
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

