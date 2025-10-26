#!/bin/bash
# PythonAnywhere Deployment Script
# Run this in your PythonAnywhere Bash console

set -e  # Exit on any error

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  Futura - PythonAnywhere Deployment                        ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Get PythonAnywhere username
if [ -z "$USER" ]; then
    echo "❌ Error: USER variable not set"
    exit 1
fi

PA_USERNAME=$USER
echo "👤 Username: $PA_USERNAME"
echo ""

# Step 1: Clone from GitHub
echo "📦 Step 1/5: Cloning from GitHub..."
cd ~
if [ -d "TVB_Workshops" ]; then
    echo "⚠️  Directory already exists. Pulling latest changes..."
    cd TVB_Workshops
    git pull origin main
else
    git clone https://github.com/yyqfrank420/polymarketapp.git TVB_Workshops
    cd TVB_Workshops
fi
echo "✅ Code downloaded"
echo ""

# Step 2: Install dependencies
echo "📚 Step 2/5: Installing Python packages..."
pip3.10 install --user -r requirements.txt
echo "✅ Dependencies installed"
echo ""

# Step 3: Initialize database
echo "🗄️  Step 3/5: Initializing database..."
if [ -f "waitinglist.db" ]; then
    echo "⚠️  Database already exists. Skipping initialization."
else
    python3.10 -c "from waitinglist_app import init_db; init_db()"
    echo "✅ Database created"
fi
echo ""

# Step 4: Set permissions
echo "🔒 Step 4/5: Setting file permissions..."
if [ -f "waitinglist.db" ]; then
    chmod 644 waitinglist.db
fi
chmod +x setup_pythonanywhere.sh
echo "✅ Permissions set"
echo ""

# Step 5: Test database connection
echo "🔍 Step 5/5: Testing setup..."
python3.10 -c "from waitinglist_app import get_db; conn = get_db(); conn.close(); print('✅ Database connection successful')"
echo ""

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  Backend Setup Complete! ✅                                 ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "📋 Next Steps (Manual - use Web Interface):"
echo ""
echo "1. Go to PythonAnywhere Web tab:"
echo "   👉 https://www.pythonanywhere.com/user/$PA_USERNAME/webapps"
echo ""
echo "2. Click 'Add a new web app'"
echo ""
echo "3. Choose 'Manual configuration' → Python 3.10"
echo ""
echo "4. Configure WSGI file:"
echo "   - Click on WSGI configuration file link"
echo "   - Delete ALL existing content"
echo "   - Copy and paste this:"
echo ""
echo "─────────────────────────────────────────────────────────────"
cat << 'WSGI_EOF'
import sys
import os

# IMPORTANT: Replace 'YOURUSERNAME' with your actual username
project_home = '/home/YOURUSERNAME/TVB_Workshops'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ['FLASK_ENV'] = 'production'

from waitinglist_app import app as application
WSGI_EOF
echo "─────────────────────────────────────────────────────────────"
echo ""
echo "   ⚠️  REPLACE 'YOURUSERNAME' with: $PA_USERNAME"
echo ""
echo "5. Add Static Files mapping:"
echo "   URL: /static/"
echo "   Directory: /home/$PA_USERNAME/TVB_Workshops/static/"
echo ""
echo "6. Click 'Reload' button"
echo ""
echo "7. Visit your site:"
echo "   🌐 https://$PA_USERNAME.pythonanywhere.com"
echo ""
echo "────────────────────────────────────────────────────────────"
echo "Database stats:"
python3.10 db_manager.py stats 2>/dev/null || echo "0 registrations"
echo "────────────────────────────────────────────────────────────"
echo ""
echo "🎉 Ready to configure your web app!"