# 🔐 Environment Variables Setup

## Local Development

### 1. Create .env file
```bash
python setup_env.py
```

### 2. Edit .env file with your actual Stripe keys
```bash
# Stripe Configuration
STRIPE_SECRET_KEY=sk_test_your_actual_secret_key_here
STRIPE_PUBLISHABLE_KEY=pk_test_your_actual_publishable_key_here
STRIPE_PRODUCT_ID=prod_your_actual_product_id_here

# Flask Configuration
FLASK_ENV=development
SECRET_KEY=your_secret_key_here
```

### 3. Run the application
```bash
python waitinglist_app.py
```

## PythonAnywhere Deployment

### 1. Set Environment Variables in PythonAnywhere

In your PythonAnywhere **Web** tab:

1. Go to **Environment variables** section
2. Add these variables:

```
STRIPE_SECRET_KEY = sk_test_your_actual_secret_key_here
STRIPE_PUBLISHABLE_KEY = pk_test_your_actual_publishable_key_here
STRIPE_PRODUCT_ID = prod_your_actual_product_id_here
FLASK_ENV = production
SECRET_KEY = your_production_secret_key_here
```

### 2. Reload your web app

Click the **Reload** button in the Web tab.

## Security Notes

- ✅ `.env` file is gitignored (never committed)
- ✅ No secrets in code
- ✅ Environment variables for all sensitive data
- ✅ Validation ensures required variables are set

## Your Stripe Keys

For this project, use:
- **Secret Key**: `sk_test_51SMPehGf9P1kk0BnS9ypd2cPraRWqPfQtJHhPTcpcpuQHIkBxVjcRy1ubNJvkwCBkeYEZ5m9Es5gMWUZfxXonObj00ggxVBZmU`
- **Publishable Key**: `pk_test_51SMPehGf9P1kk0Bn6fixDPguXM8bSxEJy6F7wTmzQB7mVQtzEkFBpqg9xenscQDVArnvwfgBBUEn4IRVKNEUEBgj000B6a9RPe`
- **Product ID**: `prod_TJ1v4b9S6EUxIQ`
