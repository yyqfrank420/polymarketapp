#!/usr/bin/env python3
"""
Specific test for "yes" response fix - tests market ID extraction from context
"""
import sys
import os
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.chatbot_service import get_chatbot_service

def test_yes_responses():
    """Test that 'yes' responses correctly extract market IDs"""
    chatbot = get_chatbot_service()
    
    if not chatbot.is_configured():
        print("❌ Chatbot not configured")
        return
    
    print("=" * 70)
    print("TESTING 'YES' RESPONSE FIX")
    print("=" * 70)
    
    test_cases = [
        {
            "name": "Football -> Yes -> Should show odds",
            "messages": [
                "football",
                "yes",
            ]
        },
        {
            "name": "Sports markets -> Yes -> Should show specific market odds",
            "messages": [
                "show me sports markets",
                "yes",
            ]
        },
        {
            "name": "Specific market mentioned -> Yes -> Should show that market's odds",
            "messages": [
                "show me market 1044",
                "yes",
            ]
        },
        {
            "name": "Multiple markets shown -> Yes -> Should show first market's odds",
            "messages": [
                "show me all markets",
                "yes",
            ]
        }
    ]
    
    for test_case in test_cases:
        print(f"\n{'='*70}")
        print(f"TEST: {test_case['name']}")
        print(f"{'='*70}")
        
        thread_id = chatbot.create_thread()
        
        for i, msg in enumerate(test_case['messages'], 1):
            print(f"\n[{i}] User: {msg}")
            response, thread_id, function_called = chatbot.chat(msg, wallet=None, thread_id=thread_id)
            
            # Check if Market ID is mentioned
            import re
            market_ids = re.findall(r'Market ID[:\s]+(\d+)', response, re.IGNORECASE)
            if market_ids:
                print(f"   📌 Market IDs found in response: {market_ids}")
            
            print(f"   Function: {function_called}")
            print(f"   Response: {response[:150]}...")
            
            # Check context
            messages = chatbot.get_thread(thread_id)
            print(f"   📚 Context: {len(messages)} messages")
            
            # If this is a "yes" response, check if it called get_market_odds
            if msg.lower() == "yes" and function_called:
                if function_called == "get_market_odds":
                    print(f"   ✅ CORRECT: Called get_market_odds!")
                else:
                    print(f"   ⚠️  Called {function_called} instead of get_market_odds")
            elif msg.lower() == "yes" and not function_called:
                print(f"   ❌ ERROR: 'yes' response didn't call any function!")
                print(f"   Response: {response[:200]}")

if __name__ == '__main__':
    test_yes_responses()

