"""Database utilities with proper connection management"""
import sqlite3
import threading
from contextlib import contextmanager
from config import Config

# Thread-local storage for connections
_local = threading.local()

def get_db():
    """Get database connection (thread-safe, optimized for concurrency)"""
    if not hasattr(_local, 'conn'):
        _local.conn = sqlite3.connect(Config.DATABASE_PATH, timeout=30.0)  # 30 second timeout
        _local.conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrent access (30 users)
        _local.conn.execute('PRAGMA journal_mode=WAL')
        _local.conn.execute('PRAGMA busy_timeout=30000')  # 30 second busy timeout
        _local.conn.execute('PRAGMA synchronous=NORMAL')  # Faster writes, still safe
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
    conn = sqlite3.connect(Config.DATABASE_PATH, timeout=30.0)
    cursor = conn.cursor()
    
    # Enable WAL mode for better concurrent access
    cursor.execute('PRAGMA journal_mode=WAL')
    cursor.execute('PRAGMA busy_timeout=30000')
    
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
                last_login DATETIME,
                auth_status TEXT DEFAULT 'unverified' CHECK(auth_status IN ('unverified', 'verified', 'rejected'))
            )
        ''')
        
        # Add auth_status column to existing users table if it doesn't exist
        try:
            cursor.execute('ALTER TABLE users ADD COLUMN auth_status TEXT DEFAULT "unverified" CHECK(auth_status IN ("unverified", "verified", "rejected"))')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Market state table for LMSR
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_state (
                market_id INTEGER PRIMARY KEY,
                q_yes REAL DEFAULT 0.0,
                q_no REAL DEFAULT 0.0,
                FOREIGN KEY(market_id) REFERENCES markets(id)
            )
        ''')
        
        # KYC verifications table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS kyc_verifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','verified','rejected')),
                full_name TEXT,
                date_of_birth TEXT,
                expiry_date TEXT,
                document_number TEXT,
                nationality TEXT,
                document_type TEXT,
                is_official_document BOOLEAN,
                verification_notes TEXT,
                verified_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(wallet) REFERENCES users(wallet)
            )
        ''')
        
        # Add expiry_date column if it doesn't exist (for existing databases)
        try:
            cursor.execute('ALTER TABLE kyc_verifications ADD COLUMN expiry_date TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        conn.commit()
    finally:
        conn.close()

def _row_to_dict(row):
    """Convert SQLite row to dictionary"""
    return {k: row[k] for k in row.keys()}

