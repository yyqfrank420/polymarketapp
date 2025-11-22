"""Input validation utilities"""
import re
from functools import wraps
from flask import jsonify

def validate_market_id(f):
    """Decorator to validate market_id parameter"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        market_id = kwargs.get('market_id')
        if not isinstance(market_id, int) or market_id <= 0:
            return jsonify({'error': 'Invalid market_id'}), 400
        return f(*args, **kwargs)
    return wrapper

def validate_wallet_address(wallet):
    """Validate Ethereum wallet address format"""
    if not wallet or not isinstance(wallet, str):
        return False
    # Basic Ethereum address validation (0x + 40 hex chars)
    pattern = r'^0x[a-fA-F0-9]{40}$'
    return bool(re.match(pattern, wallet))

def validate_amount(amount):
    """Validate bet amount"""
    try:
        amount_float = float(amount)
        return amount_float > 0 and amount_float <= 1000000  # Max $1M
    except (ValueError, TypeError):
        return False

def validate_side(side):
    """Validate bet side"""
    return side in ['YES', 'NO']

def validate_email(email):
    """Validate email format"""
    if not email or not isinstance(email, str):
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def standard_error_response(message, status_code=400):
    """Standardized error response format"""
    return jsonify({'error': message}), status_code

def standard_success_response(data=None, message=None, status_code=200):
    """Standardized success response format"""
    response = {}
    if data:
        response.update(data)
    if message:
        response['message'] = message
    return jsonify(response), status_code

