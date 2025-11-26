#!/usr/bin/env python3
"""
Test chatbot with chain prompts to verify context handling and intelligence
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.chatbot_service import get_chatbot_service

def test_chain_prompts():
    """Test chatbot with a chain of related prompts"""
    chatbot = get_chatbot_service()
    
    if not chatbot.is_configured():
        print("❌ Chatbot not configured. Set OPENAI_API_KEY in .env")
        return
    
    print("=" * 60)
    print("Testing Chatbot Chain Prompts")
    print("=" * 60)
    
    # Create a new thread
    thread_id = chatbot.create_thread()
    print(f"\n📝 Created thread: {thread_id}\n")
    
    # Chain of prompts
    prompts = [
        "hi! I want a market about football",
        "yes",
        "what about the Six Nations?",
        "show me the odds",
        "what other sports markets do you have?"
    ]
    
    for i, prompt in enumerate(prompts, 1):
        print(f"\n{'='*60}")
        print(f"Turn {i}: User says: \"{prompt}\"")
        print(f"{'='*60}")
        
        response, thread_id, function_called = chatbot.chat(prompt, wallet=None, thread_id=thread_id)
        
        print(f"\n🤖 Assistant: {response}")
        if function_called:
            print(f"   🔧 Function called: {function_called}")
        
        # Get thread history to verify context
        messages = chatbot.get_thread(thread_id)
        print(f"\n📚 Context window: {len(messages)} messages stored")
        print(f"   Last 3 messages:")
        for msg in messages[-3:]:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')[:60]
            print(f"     {role}: {content}...")
    
    print(f"\n{'='*60}")
    print("✅ Chain test complete!")
    print(f"   Total messages in thread: {len(chatbot.get_thread(thread_id))}")
    print(f"{'='*60}")

if __name__ == '__main__':
    test_chain_prompts()

