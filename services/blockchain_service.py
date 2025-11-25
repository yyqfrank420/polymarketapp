"""Blockchain service - Sepolia testnet integration"""
import json
import logging
import os

from config import Config

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
        self.account = None
        self.contract_address = None
        self.contract_metadata = {}
        self._initialize()

    def _initialize(self):
        """Initialize Web3 connection and contract metadata"""
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
                self.w3 = None
                return

            # Load contract metadata / address information
            self.contract_metadata = self._load_contract_metadata()
            metadata_address = (self.contract_metadata or {}).get('address')
            contract_address = metadata_address or Config.CONTRACT_ADDRESS
            if contract_address:
                try:
                    self.contract_address = Web3.to_checksum_address(contract_address)
                except Exception as exc:
                    logger.error(f"Invalid contract address {contract_address}: {exc}")
                    self.contract_address = None
            else:
                logger.warning("Contract address not provided in metadata or Config")

            # Initialize signer account
            if Config.PRIVATE_KEY:
                if not ETH_ACCOUNT_AVAILABLE:
                    logger.warning("eth_account not available - install with: pip install eth-account")
                else:
                    self.account = Account.from_key(Config.PRIVATE_KEY)
                    logger.info(f"Blockchain account initialized: {self.account.address}")

        except Exception as e:
            logger.error(f"Blockchain initialization error: {e}", exc_info=True)

    def is_configured(self):
        """Check if blockchain is properly configured"""
        return bool(self.w3 and self.w3.is_connected() and self.contract_address)

    def create_market_on_chain(self, question, description, end_date_timestamp):
        """Create market on blockchain."""
        if not self.is_configured():
            missing = []
            if not Config.SEPOLIA_RPC_URL:
                missing.append("SEPOLIA_RPC_URL")
            if not (self.contract_address or Config.CONTRACT_ADDRESS):
                missing.append("CONTRACT_ADDRESS")
            return False, None, f"Blockchain not configured. Missing: {', '.join(missing) or 'unknown'}"

        if not self.account:
            return False, None, "Private key not configured for transactions"

        try:
            abi = self._load_contract_abi()
            contract = self.w3.eth.contract(address=self.contract_address, abi=abi)

            nonce = self.w3.eth.get_transaction_count(self.account.address)

            try:
                gas_estimate = contract.functions.createMarket(
                    question,
                    description,
                    end_date_timestamp
                ).estimate_gas({'from': self.account.address})
                gas_limit = int(gas_estimate * 1.2)
            except Exception as gas_error:
                logger.warning(f"Gas estimation failed: {gas_error}, using default")
                gas_limit = 500_000

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

            if not ETH_ACCOUNT_AVAILABLE:
                return False, None, "eth_account package required for signing transactions. Install with: pip install eth-account"

            signed_txn = self.account.sign_transaction(transaction)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            logger.info(f"Transaction sent: {tx_hash.hex()}")
            return True, tx_hash.hex(), None

        except FileNotFoundError:
            logger.error("Contract ABI not found. Please compile the contract first: npm run compile")
            return False, None, "Contract ABI not found. Run 'npm run compile' to generate ABI"
        except Exception as e:
            logger.error(f"Blockchain transaction error: {e}", exc_info=True)
            return False, None, f"Transaction failed: {str(e)}"

    def resolve_market_on_chain(self, market_id, resolution):
        """Resolve market on blockchain (not yet implemented)."""
        if not self.is_configured():
            return False, None, "Blockchain not configured"
        return False, None, "Not implemented"

    def get_market_from_chain(self, market_id):
        """Get market data from blockchain"""
        if not self.is_configured():
            return None
        return None

    def _load_contract_metadata(self):
        """Load deployed contract metadata JSON if available."""
        candidates = []
        if Config.CONTRACT_METADATA_PATH:
            candidates.append(Config.CONTRACT_METADATA_PATH)
        service_root = os.path.dirname(os.path.dirname(__file__))
        candidates.append(os.path.join(service_root, 'deployed', 'sepolia-latest.json'))
        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                try:
                    with open(candidate, 'r') as f:
                        metadata = json.load(f)
                        if 'artifactPath' not in metadata and 'artifact_path' in metadata:
                            metadata['artifactPath'] = metadata['artifact_path']
                        return metadata
                except Exception as exc:
                    logger.warning(f"Failed to load contract metadata from {candidate}: {exc}")
        return {}

    def _resolve_artifacts_path(self):
        """Return best-effort path to compiled contract artifact."""
        metadata_path = (self.contract_metadata or {}).get('artifactPath')
        base_dir = os.path.dirname(os.path.dirname(__file__))
        candidates = []
        if metadata_path:
            if os.path.isabs(metadata_path):
                candidates.append(metadata_path)
            else:
                candidates.append(os.path.join(base_dir, metadata_path))
        service_dir = os.path.dirname(__file__)
        candidates.extend([
            os.path.join(service_dir, '..', 'artifacts', 'contracts', 'PredictionMarket.sol', 'PredictionMarket.json'),
            os.path.join(service_dir, '..', '..', 'artifacts', 'contracts', 'PredictionMarket.sol', 'PredictionMarket.json')
        ])
        for path in candidates:
            if path and os.path.exists(path):
                return os.path.normpath(path)
        return None

    def _load_contract_abi(self):
        """Load ABI from artifact or fall back to minimal interface."""
        artifacts_path = self._resolve_artifacts_path()
        if artifacts_path:
            with open(artifacts_path, 'r') as f:
                contract_data = json.load(f)
                abi = contract_data.get('abi')
                if abi:
                    return abi
        logger.info("Using minimal ABI - compile contract for full ABI support")
        return [{
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


_blockchain_service = None


def get_blockchain_service():
    """Get blockchain service instance (singleton)"""
    global _blockchain_service
    if _blockchain_service is None:
        _blockchain_service = BlockchainService()
    return _blockchain_service
