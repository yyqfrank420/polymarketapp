#!/bin/bash
# Quick setup script for PythonAnywhere
# Run this in your PythonAnywhere Bash console after uploading files

set -e  # Exit on error

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  YourGroupPredictionMarket - PythonAnywhere Setup           ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check if we're in the right directory
if [ ! -f "waitinglist_app.py" ]; then
    echo "❌ Error: waitinglist_app.py not found!"
    echo "Please navigate to the TVB_Workshops directory first:"
    echo "   cd ~/TVB_Workshops"
    exit 1
fi

echo "📦 Step 1: Installing Python packages..."
pip3.10 install --user -r requirements.txt
echo "✅ Packages installed"
echo ""

echo "🗄️  Step 2: Initializing database..."
if [ -f "waitinglist.db" ]; then
    echo "⚠️  Database already exists. Skipping initialization."
else
    python3.10 -c "from waitinglist_app import init_db; init_db()"
    echo "✅ Database created"
fi
echo ""

echo "🔐 Step 3: Setting file permissions..."
if [ -f "waitinglist.db" ]; then
    chmod 644 waitinglist.db
    echo "✅ Database permissions set"
fi
echo ""

echo "🎯 Step 4: Testing database connection..."
python3.10 -c "from waitinglist_app import get_db; conn = get_db(); conn.close(); print('✅ Database connection successful')"
echo ""

echo "📊 Step 5: Checking database..."
python3.10 db_manager.py stats
echo ""

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Setup Complete!                                             ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo "1. Configure your WSGI file in the Web tab"
echo "2. Set up static file mappings"
echo "3. Click 'Reload' on your web app"
echo "4. Visit your site at https://YOURUSERNAME.pythonanywhere.com"
echo ""
echo "See PYTHONANYWHERE_DEPLOYMENT.md for detailed instructions."
echo ""

