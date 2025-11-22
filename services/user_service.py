"""User balance management service"""
import threading
from utils.database import get_db, db_transaction
from config import Config

# Thread-safe balance operations
_balance_lock = threading.Lock()

def get_user_balance(wallet):
    """Get user balance, create user if doesn't exist (atomic operation)"""
    with _balance_lock:
        with db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT balance FROM users WHERE wallet=?', (wallet,))
            row = cursor.fetchone()
            
            if not row:
                # First time user - credit them with fake crypto
                cursor.execute('''
                    INSERT INTO users (wallet, balance, last_login)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                ''', (wallet, Config.INITIAL_FAKE_CRYPTO_BALANCE))
                return Config.INITIAL_FAKE_CRYPTO_BALANCE
            
            return row['balance'] or 0.0

def update_user_balance(wallet, amount, operation='deduct'):
    """Update user balance atomically (deduct or add)"""
    with _balance_lock:
        with db_transaction() as conn:
            cursor = conn.cursor()
            
            # Get current balance in same transaction
            cursor.execute('SELECT balance FROM users WHERE wallet=?', (wallet,))
            row = cursor.fetchone()
            current_balance = row['balance'] if row else 0.0
            
            if operation == 'deduct':
                new_balance = max(0, current_balance - amount)
            else:  # add
                new_balance = current_balance + amount
            
            cursor.execute('''
                INSERT INTO users (wallet, balance, last_login)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(wallet) DO UPDATE SET 
                    balance=?, 
                    last_login=CURRENT_TIMESTAMP
            ''', (wallet, new_balance, new_balance))
            
            return new_balance

def check_user_exists(wallet):
    """Check if user exists"""
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT wallet FROM users WHERE wallet=?', (wallet,))
        return cursor.fetchone() is not None
    finally:
        pass  # Connection managed by Flask

