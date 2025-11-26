#!/usr/bin/env python3
"""
Script to add Irish-themed markets for Ireland localization demo.
Validates image URLs before inserting to avoid broken images.
"""
import sys
import os
import requests
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.database import get_db, db_transaction
from services.market_service import get_market_state

def check_image_url(url):
    """Check if image URL is accessible"""
    if not url or url.strip() == '':
        return False
    try:
        response = requests.head(url, timeout=5, allow_redirects=True)
        content_type = response.headers.get('Content-Type', '').lower()
        return response.status_code == 200 and ('image' in content_type or 'jpeg' in content_type or 'png' in content_type)
    except:
        return False

def create_irish_markets():
    """Create Irish-themed prediction markets"""
    
    irish_markets = [
        {
            'question': 'Will Ireland win the 2025 Six Nations Championship?',
            'description': 'Ireland has been dominant in recent years. Will they secure another Six Nations title in 2025?',
            'category': 'sports',
            'image_url': 'https://images.unsplash.com/photo-1574629810360-7efbbe195018?w=800&h=400&fit=crop',
            'end_date': '2025-03-15'
        },
        {
            'question': 'Will Dublin host the 2026 European Capital of Culture?',
            'description': 'Dublin is bidding to become European Capital of Culture in 2026. Will they win the bid?',
            'category': 'politics',
            'image_url': 'https://images.unsplash.com/photo-1559827260-dc66d52bef19?w=800&h=400&fit=crop',
            'end_date': '2025-12-31'
        },
        {
            'question': 'Will the Irish economy grow by more than 3% in 2025?',
            'description': 'Ireland\'s GDP growth forecast. Will the economy exceed 3% growth this year?',
            'category': 'economics',
            'image_url': 'https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=800&h=400&fit=crop',
            'end_date': '2025-12-31'
        },
        {
            'question': 'Will Ireland legalize assisted dying before 2026?',
            'description': 'Assisted dying legislation is being debated in the Dáil. Will it pass before 2026?',
            'category': 'politics',
            'image_url': 'https://images.unsplash.com/photo-1450101499163-c8848c66ca85?w=800&h=400&fit=crop',
            'end_date': '2025-12-31'
        },
        {
            'question': 'Will the Dublin MetroLink break ground in 2025?',
            'description': 'The long-awaited MetroLink project connecting Dublin Airport to the city center.',
            'category': 'infrastructure',
            'image_url': 'https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=800&h=400&fit=crop',
            'end_date': '2025-12-31'
        },
        {
            'question': 'Will Ireland qualify for the 2026 FIFA World Cup?',
            'description': 'Can the Boys in Green secure a spot in the expanded 48-team World Cup?',
            'category': 'sports',
            'image_url': 'https://images.unsplash.com/photo-1574629810360-7efbbe195018?w=800&h=400&fit=crop',
            'end_date': '2025-12-31'
        },
        {
            'question': 'Will Ireland reach 100% renewable electricity by 2030?',
            'description': 'Ireland\'s ambitious climate targets. Will they achieve 100% renewable electricity generation?',
            'category': 'environment',
            'image_url': 'https://images.unsplash.com/photo-1466611653911-95081537e5b7?w=800&h=400&fit=crop',
            'end_date': '2030-12-31'
        },
        {
            'question': 'Will the housing crisis improve in Dublin by end of 2025?',
            'description': 'Dublin\'s housing shortage and affordability crisis. Will we see meaningful improvement?',
            'category': 'economics',
            'image_url': 'https://images.unsplash.com/photo-1560518883-ce09059eeffa?w=800&h=400&fit=crop',
            'end_date': '2025-12-31'
        },
        {
            'question': 'Will Ireland win a medal at the 2025 World Athletics Championships?',
            'description': 'Irish athletes have been performing well internationally. Will they medal in Budapest?',
            'category': 'sports',
            'image_url': 'https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=800&h=400&fit=crop',
            'end_date': '2025-08-31'
        },
        {
            'question': 'Will the Irish language requirement be removed from the Leaving Cert?',
            'description': 'Debate over mandatory Irish language in secondary education. Will the requirement be dropped?',
            'category': 'education',
            'image_url': 'https://images.unsplash.com/photo-1503676260728-1c00da094a0b?w=800&h=400&fit=crop',
            'end_date': '2025-12-31'
        },
        {
            'question': 'Will Ireland host the 2027 Ryder Cup?',
            'description': 'Ireland is bidding to host the prestigious golf tournament. Will they win the bid?',
            'category': 'sports',
            'image_url': 'https://images.unsplash.com/photo-1535131749006-b7f58c99034b?w=800&h=400&fit=crop',
            'end_date': '2025-12-31'
        },
        {
            'question': 'Will the average house price in Dublin drop below €400k in 2025?',
            'description': 'Dublin house prices have been rising. Will we see a correction bringing average prices below €400k?',
            'category': 'economics',
            'image_url': 'https://images.unsplash.com/photo-1560518883-ce09059eeffa?w=800&h=400&fit=crop',
            'end_date': '2025-12-31'
        },
        {
            'question': 'Will Ireland\'s population exceed 5.5 million by 2026?',
            'description': 'Ireland\'s population has been growing steadily. Will it cross the 5.5 million mark?',
            'category': 'demographics',
            'image_url': 'https://images.unsplash.com/photo-1559827260-dc66d52bef19?w=800&h=400&fit=crop',
            'end_date': '2026-12-31'
        },
        {
            'question': 'Will the Irish government introduce a universal basic income pilot?',
            'description': 'Universal basic income is being discussed. Will Ireland launch a pilot program?',
            'category': 'politics',
            'image_url': 'https://images.unsplash.com/photo-1450101499163-c8848c66ca85?w=800&h=400&fit=crop',
            'end_date': '2025-12-31'
        },
        {
            'question': 'Will Ireland win Eurovision 2025?',
            'description': 'Ireland has won Eurovision 7 times. Will they add an 8th victory in 2025?',
            'category': 'entertainment',
            'image_url': 'https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?w=800&h=400&fit=crop',
            'end_date': '2025-05-31'
        }
    ]
    
    print(f"Creating {len(irish_markets)} Irish-themed markets...")
    print("=" * 60)
    
    created = 0
    skipped = 0
    
    with db_transaction() as conn:
        cursor = conn.cursor()
        
        for market in irish_markets:
            # Check if market already exists
            cursor.execute('SELECT id FROM markets WHERE question=?', (market['question'],))
            if cursor.fetchone():
                print(f"⏭️  SKIP: '{market['question'][:50]}...' (already exists)")
                skipped += 1
                continue
            
            # Validate image URL
            image_url = market['image_url']
            if not check_image_url(image_url):
                print(f"⚠️  WARNING: Image URL failed validation for '{market['question'][:50]}...'")
                print(f"   Using placeholder instead")
                image_url = 'https://via.placeholder.com/800x400/1E293B/3B82F6?text=Irish+Market'
            
            # Insert market
            cursor.execute('''
                INSERT INTO markets (question, description, image_url, category, end_date, created_by, status)
                VALUES (?, ?, ?, ?, ?, ?, 'open')
            ''', (
                market['question'],
                market['description'],
                image_url,
                market['category'],
                market['end_date'],
                'script'
            ))
            
            market_id = cursor.lastrowid
            
            # Initialize market state with LMSR buffer
            from config import Config
            cursor.execute('''
                INSERT INTO market_state (market_id, q_yes, q_no)
                VALUES (?, ?, ?)
            ''', (market_id, Config.LMSR_BUFFER, Config.LMSR_BUFFER))
            
            print(f"✅ CREATED: '{market['question'][:50]}...' (ID: {market_id})")
            created += 1
    
    print("=" * 60)
    print(f"✅ Created: {created} markets")
    print(f"⏭️  Skipped: {skipped} markets (already exist)")
    print(f"📊 Total: {len(irish_markets)} markets processed")

if __name__ == '__main__':
    create_irish_markets()

