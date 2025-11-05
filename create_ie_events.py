#!/usr/bin/env python3
"""
Script to create IE University related prediction markets
"""
import requests
import json

BASE_URL = "http://localhost:5001"

IE_MARKETS = [
    {
        "question": "Will IE University rank in the top 3 business schools in Spain by 2026?",
        "description": "Based on QS World University Rankings and Financial Times rankings. Market resolves on Dec 31, 2026.",
        "category": "Education",
        "image_url": "https://images.unsplash.com/photo-1562774053-701939374585?w=800",
        "end_date": "2026-12-31"
    },
    {
        "question": "Will IE launch a new campus in Asia before 2027?",
        "description": "Market resolves if IE University announces and opens a new campus in any Asian country before Jan 1, 2027.",
        "category": "Education",
        "image_url": "https://images.unsplash.com/photo-1541339907198-e08756dedf3f?w=800",
        "end_date": "2027-01-01"
    },
    {
        "question": "Will IE's MBA program exceed 500 students enrolled in 2025?",
        "description": "Based on official enrollment numbers for the 2025 academic year. Market resolves by Dec 31, 2025.",
        "category": "Education",
        "image_url": "https://images.unsplash.com/photo-1523050854058-8df90110c9f1?w=800",
        "end_date": "2025-12-31"
    },
    {
        "question": "Will IE partner with a major tech company for AI research by end of 2025?",
        "description": "Partnership must be publicly announced with major tech companies (Google, Microsoft, Meta, OpenAI, etc.) before Jan 1, 2026.",
        "category": "Science",
        "image_url": "https://images.unsplash.com/photo-1485827404703-89b55fcc595e?w=800",
        "end_date": "2025-12-31"
    },
    {
        "question": "Will IE's sustainability program win a major international award in 2025?",
        "description": "Awards include: AACSB Innovation Award, EFMD Excellence Award, or similar international recognition. Market resolves by Dec 31, 2025.",
        "category": "Education",
        "image_url": "https://images.unsplash.com/photo-1473341304170-971dccb5ac1e?w=800",
        "end_date": "2025-12-31"
    },
    {
        "question": "Will IE launch a blockchain or cryptocurrency course in 2025?",
        "description": "Must be a full course (not just a module) offered in the 2025 academic year. Market resolves by Dec 31, 2025.",
        "category": "Crypto",
        "image_url": "https://images.unsplash.com/photo-1639762681485-074b7f938ba0?w=800",
        "end_date": "2025-12-31"
    },
    {
        "question": "Will IE's online programs enrollment exceed 2000 students in 2025?",
        "description": "Based on official enrollment data for all online degree programs combined. Market resolves by Dec 31, 2025.",
        "category": "Education",
        "image_url": "https://images.unsplash.com/photo-1522202176988-66273c2fd55f?w=800",
        "end_date": "2025-12-31"
    },
    {
        "question": "Will IE University be featured in Financial Times Top 10 European Business Schools in 2025?",
        "description": "Based on Financial Times European Business School Rankings 2025. Market resolves when rankings are published.",
        "category": "Education",
        "image_url": "https://images.unsplash.com/photo-1497633762265-9d179a990aa6?w=800",
        "end_date": "2025-12-31"
    }
]

def create_market(market_data):
    """Create a single market"""
    url = f"{BASE_URL}/api/markets"
    headers = {"Content-Type": "application/json"}
    payload = {
        **market_data,
        "created_by": "IE University Admin"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        if data.get('success'):
            print(f"✅ Created: {market_data['question'][:60]}...")
            return data.get('market_id')
        else:
            print(f"❌ Failed: {data.get('message', 'Unknown error')}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Error creating market: {e}")
        return None

def main():
    print("Creating IE University prediction markets...\n")
    
    created_count = 0
    for market in IE_MARKETS:
        market_id = create_market(market)
        if market_id:
            created_count += 1
    
    print(f"\n✨ Successfully created {created_count} out of {len(IE_MARKETS)} markets!")

if __name__ == "__main__":
    main()

