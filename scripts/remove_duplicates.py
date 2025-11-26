#!/usr/bin/env python3
"""
Script to remove duplicate markets, keeping the oldest one (lowest ID).
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.database import get_db, db_transaction

def remove_duplicate_markets():
    """Remove duplicate markets, keeping the oldest (lowest ID)"""
    
    with db_transaction() as conn:
        cursor = conn.cursor()
        
        # Find duplicates by question
        cursor.execute('''
            SELECT question, COUNT(*) as count, GROUP_CONCAT(id ORDER BY id) as ids
            FROM markets
            GROUP BY question
            HAVING count > 1
            ORDER BY count DESC
        ''')
        
        duplicates = cursor.fetchall()
        
        if not duplicates:
            print("✅ No duplicate markets found!")
            return
        
        print(f"Found {len(duplicates)} duplicate questions:")
        print("=" * 60)
        
        total_deleted = 0
        
        for row in duplicates:
            question = row['question']
            ids = [int(x) for x in row['ids'].split(',')]
            keep_id = ids[0]  # Keep the oldest (lowest ID)
            delete_ids = ids[1:]  # Delete the rest
            
            print(f"\nQuestion: {question[:60]}...")
            print(f"  Keeping ID: {keep_id}")
            print(f"  Deleting IDs: {delete_ids}")
            
            # Delete bets for duplicate markets first (foreign key constraint)
            for market_id in delete_ids:
                cursor.execute('DELETE FROM bets WHERE market_id=?', (market_id,))
                bets_deleted = cursor.rowcount
                if bets_deleted > 0:
                    print(f"    Deleted {bets_deleted} bets for market {market_id}")
            
            # Delete market_state for duplicates
            for market_id in delete_ids:
                cursor.execute('DELETE FROM market_state WHERE market_id=?', (market_id,))
            
            # Delete duplicate markets
            for market_id in delete_ids:
                cursor.execute('DELETE FROM markets WHERE id=?', (market_id,))
                total_deleted += 1
        
        print("\n" + "=" * 60)
        print(f"✅ Deleted {total_deleted} duplicate markets")
        print(f"✅ Kept {len(duplicates)} original markets")

if __name__ == '__main__':
    remove_duplicate_markets()

