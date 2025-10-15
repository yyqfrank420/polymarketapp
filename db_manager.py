"""
Database management utility for waitinglist app
Run on PythonAnywhere Bash console to manage your database
"""

import sqlite3
import csv
import os
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, 'waitinglist.db')

def get_stats():
    """Get database statistics"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Total registrations
    cursor.execute('SELECT COUNT(*) FROM registrations')
    total = cursor.fetchone()[0]
    
    # Today's registrations
    cursor.execute('''
        SELECT COUNT(*) FROM registrations 
        WHERE DATE(timestamp) = DATE('now')
    ''')
    today = cursor.fetchone()[0]
    
    # Countries
    cursor.execute('''
        SELECT country, COUNT(*) as count 
        FROM registrations 
        WHERE country != '' 
        GROUP BY country 
        ORDER BY count DESC 
        LIMIT 5
    ''')
    countries = cursor.fetchall()
    
    conn.close()
    
    print(f"\n📊 WAITLIST STATISTICS")
    print(f"{'='*50}")
    print(f"Total Registrations: {total}")
    print(f"Today's Registrations: {today}")
    print(f"\nTop Countries:")
    for country, count in countries:
        print(f"  {country}: {count}")
    print(f"{'='*50}\n")

def export_csv(filename='registrations_export.csv'):
    """Export all registrations to CSV"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM registrations ORDER BY timestamp DESC')
    rows = cursor.fetchall()
    
    # Get column names
    cursor.execute('PRAGMA table_info(registrations)')
    columns = [col[1] for col in cursor.fetchall()]
    
    conn.close()
    
    # Write CSV
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)
    
    print(f"✅ Exported {len(rows)} registrations to {filename}")
    print(f"Download from: ~/TVB_Workshops/{filename}")

def recent_registrations(limit=10):
    """Show recent registrations"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute(f'''
        SELECT email, country, city, timestamp 
        FROM registrations 
        ORDER BY timestamp DESC 
        LIMIT {limit}
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    print(f"\n📧 RECENT {limit} REGISTRATIONS")
    print(f"{'='*80}")
    print(f"{'Email':<30} {'Location':<25} {'Date':<25}")
    print(f"{'-'*80}")
    for email, country, city, timestamp in rows:
        location = f"{city}, {country}" if city and country else (country or 'Unknown')
        print(f"{email:<30} {location:<25} {timestamp:<25}")
    print(f"{'='*80}\n")

def backup_database():
    """Create a backup of the database"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'waitinglist_backup_{timestamp}.db'
    
    import shutil
    shutil.copy2(DATABASE, backup_file)
    
    print(f"✅ Database backed up to: {backup_file}")

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("\n🛠️  Database Manager for YourGroupPredictionMarket")
        print("\nUsage:")
        print("  python3.10 db_manager.py stats          - Show statistics")
        print("  python3.10 db_manager.py recent [N]     - Show recent N registrations")
        print("  python3.10 db_manager.py export [file]  - Export to CSV")
        print("  python3.10 db_manager.py backup         - Backup database")
        sys.exit(0)
    
    command = sys.argv[1].lower()
    
    if command == 'stats':
        get_stats()
    elif command == 'recent':
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        recent_registrations(limit)
    elif command == 'export':
        filename = sys.argv[2] if len(sys.argv) > 2 else 'registrations_export.csv'
        export_csv(filename)
    elif command == 'backup':
        backup_database()
    else:
        print(f"❌ Unknown command: {command}")

