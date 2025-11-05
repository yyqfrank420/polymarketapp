#!/usr/bin/env python3
"""
Script to simulate transactions on IE University markets
"""
import requests
import time
import random
import sys

BASE_URL = "http://localhost:5001"

# Simulated wallets
WALLETS = [
    "0xIEStudent1Wallet",
    "0xIEAlumni2Address",
    "0xIEProfessor3",
    "0xIESupporter4",
    "0xIETrader5",
    "0xIEInvestor6",
]

def get_markets():
    """Get all markets"""
    try:
        response = requests.get(f"{BASE_URL}/api/markets")
        response.raise_for_status()
        data = response.json()
        return data.get('markets', [])
    except Exception as e:
        print(f"Error fetching markets: {e}")
        return []

def place_bet(market_id, wallet, side, amount):
    """Place a bet on a market"""
    url = f"{BASE_URL}/api/markets/{market_id}/bet"
    headers = {"Content-Type": "application/json"}
    payload = {
        "wallet": wallet,
        "side": side,
        "amount": amount
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        if data.get('success'):
            return True
        return False
    except Exception as e:
        return False

def simulate_ie_trading():
    """Simulate trading on IE University markets"""
    markets = get_markets()
    
    # Filter IE University markets (they contain "IE" in the question)
    ie_markets = [m for m in markets if 'IE' in m.get('question', '')]
    
    if not ie_markets:
        print("No IE University markets found!")
        return
    
    print(f"Found {len(ie_markets)} IE University markets. Simulating trades...\n")
    
    # Simulate 20-30 trades
    num_trades = random.randint(20, 30)
    
    for i in range(num_trades):
        market = random.choice(ie_markets)
        wallet = random.choice(WALLETS)
        side = random.choice(['YES', 'NO'])
        
        # Vary bet amounts
        bet_type = random.choices(['small', 'medium', 'large'], weights=[0.5, 0.3, 0.2], k=1)[0]
        if bet_type == 'small':
            amount = round(random.uniform(20, 80), 2)
        elif bet_type == 'medium':
            amount = round(random.uniform(80, 200), 2)
        else:
            amount = round(random.uniform(200, 500), 2)
        
        success = place_bet(market['id'], wallet, side, amount)
        
        if success:
            print(f"✅ {side} ${amount:.2f} on Market #{market['id']}: {market['question'][:50]}...")
        else:
            print(f"❌ Failed to place bet on Market #{market['id']}")
        
        # Random delay between bets
        time.sleep(random.uniform(0.5, 2.0))
    
    print(f"\n✨ Simulated {num_trades} trades on IE University markets!")

if __name__ == "__main__":
    simulate_ie_trading()

