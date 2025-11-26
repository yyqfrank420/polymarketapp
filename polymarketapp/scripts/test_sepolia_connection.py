#!/usr/bin/env python3
"""Test Sepolia blockchain connection"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from services.blockchain_service import get_blockchain_service

def test_sepolia_connection():
    """Test Sepolia connection and configuration"""
    print("🔗 Testing Sepolia Connection...\n")
    
    blockchain_service = get_blockchain_service()
    
    # Check configuration
    print("📋 Configuration Check:")
    print(f"  Web3 Available: {blockchain_service.w3 is not None}")
    print(f"  Is Connected: {blockchain_service.w3.is_connected() if blockchain_service.w3 else False}")
    print(f"  Contract Address: {blockchain_service.contract_address or 'Not set'}")
    print(f"  Account Address: {blockchain_service.account.address if blockchain_service.account else 'Not set'}")
    print(f"  Is Configured: {blockchain_service.is_configured()}")
    print()
    
    if not blockchain_service.is_configured():
        print("❌ Blockchain not fully configured!")
        print("\nRequired environment variables:")
        print("  - SEPOLIA_RPC_URL")
        print("  - CONTRACT_ADDRESS (or set CONTRACT_METADATA_PATH)")
        print("  - PRIVATE_KEY (for transactions)")
        return False
    
    # Test connection
    print("🌐 Connection Test:")
    try:
        if blockchain_service.w3:
            chain_id = blockchain_service.w3.eth.chain_id
            latest_block = blockchain_service.w3.eth.block_number
            gas_price = blockchain_service.w3.eth.gas_price
            
            print(f"  ✅ Connected to Sepolia!")
            print(f"  Chain ID: {chain_id}")
            print(f"  Latest Block: {latest_block}")
            print(f"  Gas Price: {gas_price / 1e9:.2f} Gwei")
            print()
            
            # Check account balance
            if blockchain_service.account:
                balance_wei = blockchain_service.w3.eth.get_balance(blockchain_service.account.address)
                balance_eth = balance_wei / 1e18
                print(f"💰 Account Balance:")
                print(f"  Address: {blockchain_service.account.address}")
                print(f"  Balance: {balance_eth:.4f} ETH")
                if balance_eth < 0.01:
                    print(f"  ⚠️  Low balance! You may need Sepolia ETH for transactions.")
                print()
            
            # Check contract
            if blockchain_service.contract_address:
                print(f"📄 Contract Check:")
                print(f"  Address: {blockchain_service.contract_address}")
                code = blockchain_service.w3.eth.get_code(blockchain_service.contract_address)
                if code and code != b'':
                    print(f"  ✅ Contract code found on chain")
                else:
                    print(f"  ⚠️  No contract code at this address")
                print()
            
            return True
        else:
            print("  ❌ Web3 not initialized")
            return False
            
    except Exception as e:
        print(f"  ❌ Connection error: {e}")
        return False

if __name__ == "__main__":
    success = test_sepolia_connection()
    sys.exit(0 if success else 1)

