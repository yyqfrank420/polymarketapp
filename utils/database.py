"""Database utilities with proper connection management"""
import sqlite3
import threading
from contextlib import contextmanager
from config import Config

# Thread-local storage for connections
_local = threading.local()

def get_db():
    """Get database connection (thread-safe)"""
    if not hasattr(_local, 'conn'):
        _local.conn = sqlite3.connect(Config.DATABASE_PATH)
        _local.conn.row_factory = sqlite3.Row
    return _local.conn

@contextmanager
def db_transaction():
    """Context manager for database transactions with automatic rollback on error"""
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        # Don't close here - let Flask handle it at request end
        pass

def close_db():
    """Close database connection for current thread"""
    if hasattr(_local, 'conn'):
        _local.conn.close()
        delattr(_local, 'conn')

def init_db():
    """Initialize database schema"""
    conn = sqlite3.connect(Config.DATABASE_PATH)
    cursor = conn.cursor()
    
    try:
        # Registrations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                latitude REAL,
                longitude REAL,
                ip_address TEXT,
                country TEXT,
                city TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Markets table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS markets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                description TEXT,
                image_url TEXT,
                category TEXT,
                end_date TEXT,
                created_by TEXT,
                status TEXT DEFAULT 'open',
                resolution TEXT,
                blockchain_tx_hash TEXT,
                contract_address TEXT,
                blockchain_market_id INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Bets table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id INTEGER NOT NULL,
                wallet TEXT NOT NULL,
                side TEXT NOT NULL CHECK(side IN ('YES','NO')),
                amount REAL NOT NULL,
                shares REAL NOT NULL,
                price_per_share REAL NOT NULL,
                tx_hash TEXT,
                signature TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(market_id) REFERENCES markets(id)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_bets_market ON bets(market_id)')
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                wallet TEXT PRIMARY KEY,
                balance REAL DEFAULT 0.0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_login DATETIME
            )
        ''')
        
        # Market state table for LMSR
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_state (
                market_id INTEGER PRIMARY KEY,
                q_yes REAL DEFAULT 0.0,
                q_no REAL DEFAULT 0.0,
                FOREIGN KEY(market_id) REFERENCES markets(id)
            )
        ''')
        
        conn.commit()
    finally:
        conn.close()

def _row_to_dict(row):
    """Convert SQLite row to dictionary"""
    return {k: row[k] for k in row.keys()}

