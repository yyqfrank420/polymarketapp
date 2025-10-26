#!/usr/bin/env python3
"""
Setup script to create .env file for local development
"""

import os

def create_env_file():
    """Create .env file with Stripe configuration"""
    
    env_content = """# Stripe Configuration
# Replace these with your actual Stripe keys
STRIPE_SECRET_KEY=your_stripe_secret_key_here
STRIPE_PUBLISHABLE_KEY=your_stripe_publishable_key_here
STRIPE_PRODUCT_ID=your_stripe_product_id_here

# Flask Configuration
FLASK_ENV=development
SECRET_KEY=dev-secret-key-change-in-production
"""
    
    with open('.env', 'w') as f:
        f.write(env_content)
    
    print("✅ Created .env file for local development")
    print("🔒 .env file is ignored by git (secure)")

if __name__ == "__main__":
    create_env_file()
