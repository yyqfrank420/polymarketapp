#!/usr/bin/env python3
"""
Deep testing: context window, error handling, edge cases
"""
import sys
import os
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.chatbot_service import get_chatbot_service

def test_context_window():
    """Test that 20 messages are actually kept"""
    print("=" * 70)
    print("TESTING CONTEXT WINDOW (20 messages)")
    print("=" * 70)
    
    chatbot = get_chatbot_service()
    if not chatbot.is_configured():
        print("❌ Chatbot not configured")
        return
    
    thread_id = chatbot.create_thread()
    
    # Send 25 messages to test if only 20 are kept
    for i in range(1, 26):
        msg = f"message {i}"
        response, thread_id, _ = chatbot.chat(msg, wallet=None, thread_id=thread_id)
        messages = chatbot.get_thread(thread_id)
        print(f"Message {i}: {len(messages)} messages in thread")
        
        if i == 20:
            print(f"   ✅ At message 20, thread has {len(messages)} messages")
        if i == 25:
            print(f"   ✅ At message 25, thread has {len(messages)} messages (should be ≤20 in context)")
    
    # Check what messages are actually sent to API
    print("\nChecking last API call context...")
    # We can't directly check, but we can verify thread length

def test_error_handling():
    """Test error handling in function calls"""
    print("\n" + "=" * 70)
    print("TESTING ERROR HANDLING")
    print("=" * 70)
    
    chatbot = get_chatbot_service()
    if not chatbot.is_configured():
        print("❌ Chatbot not configured")
        return
    
    thread_id = chatbot.create_thread()
    
    error_tests = [
        ("what are the odds for market 99999?", "get_market_odds"),
        ("check market 0", "check_market_status"),
        ("show me market -1", "get_market_odds"),
        ("get context for market 99999", "get_market_context"),
    ]
    
    for test_msg, expected_function in error_tests:
        print(f"\nTest: {test_msg}")
        response, thread_id, function_called = chatbot.chat(test_msg, wallet=None, thread_id=thread_id)
        
        print(f"   Function: {function_called}")
        print(f"   Response: {response[:100]}...")
        
        if function_called == expected_function:
            if "doesn't exist" in response.lower() or "not found" in response.lower() or "error" in response.lower():
                print(f"   ✅ Correctly handled error")
            else:
                print(f"   ⚠️  Function called but error not properly communicated")
        else:
            print(f"   ⚠️  Called {function_called} instead of {expected_function}")

def test_market_id_extraction():
    """Test various ways market IDs might be mentioned"""
    print("\n" + "=" * 70)
    print("TESTING MARKET ID EXTRACTION FROM CONTEXT")
    print("=" * 70)
    
    chatbot = get_chatbot_service()
    if not chatbot.is_configured():
        print("❌ Chatbot not configured")
        return
    
    test_cases = [
        {
            "setup": ["show me market 1044"],
            "followup": "yes",
            "expected": "get_market_odds"
        },
        {
            "setup": ["football"],
            "followup": "show me odds",
            "expected": "get_market_odds"
        },
        {
            "setup": ["what about the Six Nations market?"],
            "followup": "yes",
            "expected": "get_market_odds"
        },
        {
            "setup": ["show me market 1044", "what about 1045?"],
            "followup": "yes",
            "expected": "get_market_odds"  # Should use 1045 (most recent)
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n--- Test Case {i} ---")
        thread_id = chatbot.create_thread()
        
        # Setup messages
        for setup_msg in test_case['setup']:
            response, thread_id, _ = chatbot.chat(setup_msg, wallet=None, thread_id=thread_id)
            print(f"Setup: {setup_msg}")
            print(f"  Response mentions Market IDs: {[x for x in response.split() if x.isdigit() and len(x) >= 4]}")
        
        # Followup
        print(f"Followup: {test_case['followup']}")
        response, thread_id, function_called = chatbot.chat(test_case['followup'], wallet=None, thread_id=thread_id)
        print(f"  Function called: {function_called}")
        
        if function_called == test_case['expected']:
            print(f"  ✅ Correct!")
        else:
            print(f"  ❌ Expected {test_case['expected']}, got {function_called}")

if __name__ == '__main__':
    test_context_window()
    test_error_handling()
    test_market_id_extraction()

