#!/usr/bin/env python3
"""
Setup script to create .env file for local development
"""

import os

def create_env_file():
    """Create .env file with Stripe configuration"""
    
    env_content = """# Stripe Configuration
STRIPE_SECRET_KEY=sk_test_51SMPehGf9P1kk0BnS9ypd2cPraRWqPfQtJHhPTcpcpuQHIkBxVjcRy1ubNJvkwCBkeYEZ5m9Es5gMWUZfxXonObj00ggxVBZmU
STRIPE_PUBLISHABLE_KEY=pk_test_51SMPehGf9P1kk0Bn6fixDPguXM8bSxEJy6F7wTmzQB7mVQtzEkFBpqg9xenscQDVArnvwfgBBUEn4IRVKNEUEBgj000B6a9RPe
STRIPE_PRODUCT_ID=prod_TJ1v4b9S6EUxIQ

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
