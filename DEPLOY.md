# Deploy to PythonAnywhere

## 1. Push to GitHub
```bash
git push origin clean-stripe-integration
```

## 2. Deploy to PythonAnywhere

### Clone your repo on PythonAnywhere:
```bash
cd ~
git clone https://github.com/yyqfrank420/polymarketapp.git TVB_Workshops
cd TVB_Workshops
git checkout clean-stripe-integration
```

### Install dependencies:
```bash
pip3.10 install --user -r requirements.txt
```

### Set environment variables in PythonAnywhere Web tab:
```
STRIPE_SECRET_KEY = your_stripe_secret_key
STRIPE_PUBLISHABLE_KEY = your_stripe_publishable_key  
STRIPE_PRODUCT_ID = your_stripe_product_id
FLASK_ENV = production
```

### Configure Web App:
1. Web tab → Add new web app → Manual config → Python 3.10
2. Edit WSGI file (delete all, paste from wsgi.py, update username)
3. Add static files: `/static/` → `/home/yourusername/TVB_Workshops/static/`
4. Click Reload

Done.