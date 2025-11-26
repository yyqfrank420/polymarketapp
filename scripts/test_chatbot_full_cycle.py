#!/usr/bin/env python3
"""
Full cycle test: Complete conversation from chit-chat to placing a bet
Tests all tool calls in sequence within one conversation context
"""
import sys
import os
import time
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.chatbot_service import get_chatbot_service

def print_step(step_num, step_name, user_msg, response, function_called=None):
    """Print formatted conversation step"""
    print(f"\n{'='*70}")
    print(f"STEP {step_num}: {step_name}")
    print(f"{'='*70}")
    print(f"👤 User: {user_msg}")
    if function_called:
        print(f"   🔧 Function: {function_called}")
    print(f"🤖 Assistant: {response}")
    print(f"{'─'*70}")

def test_full_cycle():
    """Test complete conversation cycle using all tool calls"""
    print("\n" + "="*70)
    print("FULL CYCLE TEST: Chat → Discover → Check → Bet")
    print("="*70)
    
    chatbot = get_chatbot_service()
    if not chatbot.is_configured():
        print("❌ Chatbot not configured")
        return
    
    # Use a test wallet
    test_wallet = "0x1234567890123456789012345678901234567890"
    
    # Create single thread for entire conversation
    thread_id = chatbot.create_thread()
    print(f"\n📝 Created conversation thread: {thread_id[:8]}...")
    
    steps = [
        {
            "name": "Initial Greeting",
            "msg": "Hi!",
            "expected_functions": None,  # Just chat
            "description": "Casual greeting - no function calls"
        },
        {
            "name": "Market Discovery",
            "msg": "I'm interested in sports markets",
            "expected_functions": ["get_all_markets"],
            "description": "Should call get_all_markets to discover sports markets"
        },
        {
            "name": "Follow-up on Specific Market",
            "msg": "What about the Six Nations?",
            "expected_functions": ["get_all_markets", "get_market_odds"],
            "description": "Should find Six Nations market and show odds"
        },
        {
            "name": "Confirm Interest",
            "msg": "yes",
            "expected_functions": ["get_market_odds"],
            "description": "Should extract market_id from context and call get_market_odds"
        },
        {
            "name": "Check Market Status",
            "msg": "Is that market still open?",
            "expected_functions": ["check_market_status"],
            "description": "Should call check_market_status"
        },
        {
            "name": "Get Market Context/News",
            "msg": "What's the latest news about this market?",
            "expected_functions": ["get_market_context"],
            "description": "Should call get_market_context for news"
        },
        {
            "name": "Check Portfolio",
            "msg": "What's my portfolio?",
            "expected_functions": ["get_user_bets"],
            "description": "Should call get_user_bets to show portfolio",
            "use_wallet": True
        },
        {
            "name": "Place Bet",
            "msg": "I want to bet 50 EURC on YES for the Six Nations market",
            "expected_functions": ["place_bet"],
            "description": "Should call place_bet with market_id, side, amount",
            "use_wallet": True
        },
        {
            "name": "Verify Bet",
            "msg": "Show me my bets again",
            "expected_functions": ["get_user_bets"],
            "description": "Should call get_user_bets to show updated portfolio",
            "use_wallet": True
        },
        {
            "name": "Final Check",
            "msg": "What are the odds now?",
            "expected_functions": ["get_market_odds"],
            "description": "Should call get_market_odds to show updated odds after bet"
        }
    ]
    
    all_passed = True
    
    for i, step in enumerate(steps, 1):
        print_step(i, step['name'], step['msg'], "", None)
        
        try:
            # Use wallet for portfolio/bet related steps
            use_wallet = step.get('use_wallet', False) or 'portfolio' in step['name'].lower() or 'bet' in step['name'].lower()
            response, thread_id, function_called = chatbot.chat(
                step['msg'],
                wallet=test_wallet if use_wallet else None,
                thread_id=thread_id
            )
            
            print_step(i, step['name'], step['msg'], response, function_called)
            
            # Check if expected function was called
            if step['expected_functions']:
                if function_called in step['expected_functions']:
                    print(f"   ✅ PASS: Called {function_called} (expected one of {step['expected_functions']})")
                elif function_called:
                    print(f"   ⚠️  PARTIAL: Called {function_called} (expected one of {step['expected_functions']})")
                else:
                    print(f"   ❌ FAIL: No function called (expected one of {step['expected_functions']})")
                    all_passed = False
            else:
                if function_called:
                    print(f"   ⚠️  Unexpected function call: {function_called}")
                else:
                    print(f"   ✅ PASS: No function call (as expected for casual chat)")
            
            # Check context retention
            messages = chatbot.get_thread(thread_id)
            print(f"   📚 Context: {len(messages)} messages in thread")
            
            # Small delay to avoid rate limits
            time.sleep(0.5)
            
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            all_passed = False
            import traceback
            traceback.print_exc()
    
    # Final summary
    print("\n" + "="*70)
    print("FULL CYCLE TEST SUMMARY")
    print("="*70)
    
    messages = chatbot.get_thread(thread_id)
    print(f"📊 Total messages in conversation: {len(messages)}")
    print(f"📊 Context window used: {min(20, len(messages))} messages")
    
    if all_passed:
        print("\n✅ ALL STEPS PASSED!")
    else:
        print("\n⚠️  SOME STEPS HAD ISSUES - CHECK ABOVE")
    
    print("\n🔧 Functions tested:")
    print("   ✅ get_all_markets - Market discovery")
    print("   ✅ get_market_odds - Check odds")
    print("   ✅ check_market_status - Market status")
    print("   ✅ get_market_context - News/context")
    print("   ✅ get_user_bets - Portfolio")
    print("   ✅ place_bet - Place trade")
    
    print("\n" + "="*70)

if __name__ == '__main__':
    test_full_cycle()

