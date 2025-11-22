# Futura - Waitlist Landing Page

A professional, Polymarket-inspired waitlist landing page for a prediction market platform. Optimized for PythonAnywhere deployment.

![Status](https://img.shields.io/badge/status-production%20ready-green) ![Python](https://img.shields.io/badge/python-3.10-blue) ![Flask](https://img.shields.io/badge/flask-3.0-lightgrey)

---

## 🎯 Overview

**Futura** is a Polymarket-style order book prediction market. This landing page collects pre-launch registrations with email and geolocation data.

### Features

- ✅ **Polymarket-Inspired Design** - Minimalist, professional UI
- 📱 **Fully Responsive** - Mobile-first Bootstrap 5
- 🌍 **Geolocation** - Browser API + IP fallback
- 📊 **Live Counter** - Real-time registration count
- 💾 **SQLite Database** - Auto-initialized, zero config
- 🛡️ **Production Ready** - Error handling, logging, health checks
- 🚀 **GitHub Deploy** - Direct deployment from GitHub to PythonAnywhere

---

## 🚀 Quick Deploy

See **[DEPLOY.md](DEPLOY.md)** for complete deployment instructions.

**TL;DR:**
1. Push to GitHub
2. Clone on PythonAnywhere
3. Run: `bash setup_pythonanywhere.sh`
4. Configure WSGI + static files
5. Go live!

**Time**: ~10 minutes

---

## 💻 Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py

# Visit
open http://localhost:5001
```

---

## 📁 Project Structure

```
TVB_Workshops/
├── app.py                      # Main Flask application
├── db_manager.py               # Database management CLI
├── wsgi.py                     # WSGI config for PythonAnywhere
├── requirements.txt            # Python dependencies
├── setup_pythonanywhere.sh     # Auto-setup script
├── templates/
│   └── index.html             # Landing page
├── static/
│   ├── css/style.css          # Polymarket-inspired styles
│   └── js/app.js              # Geolocation + form handling
├── README.md                   # This file
└── DEPLOY.md                   # Deployment guide
```

---

## 🛠️ Database Management

```bash
# View statistics
python db_manager.py stats

# View recent registrations
python db_manager.py recent 20

# Export to CSV
python db_manager.py export registrations.csv

# Backup database
python db_manager.py backup
```

---

## 📊 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Landing page |
| `/api/register` | POST | Submit email + location |
| `/api/count` | GET | Get total registrations |
| `/health` | GET | Health check |

**Example:**
```bash
curl https://yourusername.pythonanywhere.com/api/count
# {"count": 42}
```

---

## 🎨 Design

Polymarket-inspired minimalist aesthetic:

- **Typography**: Inter font, clean hierarchy
- **Colors**: Neutral palette (white/grey) + royal blue (#4169e1)
- **Layout**: Data-driven, transparent, mobile-first
- **Animations**: Subtle transitions and hover effects

### Customization

**Change primary color** (edit `static/css/style.css`):
```css
/* Line 76 */
background-color: #4169e1;  /* Change this */
```

**Update content** (edit `templates/index.html`):
- Hero section (lines 28-35)
- NABC cards (lines 60-110)
- Footer email (line 122)

---

## 🔒 Security

- ✅ Email validation (client + server)
- ✅ SQL injection protection (parameterized queries)
- ✅ XSS protection (Flask auto-escaping)
- ✅ Duplicate prevention (unique constraints)
- ✅ Input sanitization

---

## 🗄️ Database Schema

```sql
CREATE TABLE registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    latitude REAL,
    longitude REAL,
    ip_address TEXT,
    country TEXT,
    city TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 🔄 Update Deployment

After making changes:

```bash
# Commit and push
git add .
git commit -m "Update landing page"
git push origin main

# On PythonAnywhere
cd ~/TVB_Workshops
git pull origin main
# Then reload web app in Web tab
```

---

## 🐛 Troubleshooting

### Site not loading?
```bash
# Check error logs
tail -50 /var/log/yourusername.pythonanywhere.com.error.log
```

### Database issues?
```bash
cd ~/TVB_Workshops
rm polymarket.db
python3.10 -c "from app import init_db; init_db()"
# Reload web app
```

## Blockchain Features

### Smart Contracts (Sepolia Testnet)

The platform supports hybrid blockchain integration - markets can be created on-chain for verifiable, trustless market mechanics while betting remains fast and efficient off-chain.

**Setup:**
1. Install Node.js dependencies:
   ```bash
   npm install
   ```

2. Configure environment variables in `.env`:
   ```
   INFURA_PROJECT_ID=your_infura_project_id
   SEPOLIA_RPC_URL=https://sepolia.infura.io/v3/your_project_id
   PRIVATE_KEY=your_wallet_private_key
   ```

3. Deploy contract to Sepolia:
   ```bash
   npm run deploy
   ```

4. Save the contract address to `.env` as `CONTRACT_ADDRESS`

**Features:**
- Markets can be created on Ethereum Sepolia testnet
- View markets on Etherscan for transparency
- Blockchain verification badges on market pages
- Hybrid approach: markets on-chain, bets off-chain for optimal UX

**Getting Sepolia Test ETH:**
- Use faucets: https://sepoliafaucet.com/ or https://faucet.quicknode.com/ethereum/sepolia
- Free test tokens for development

## AI Chatbot

### OpenAI-Powered Market Assistant

An intelligent chatbot available on all customer-facing pages that helps users:
- Check market odds and prices
- Place bets via natural language
- View their betting portfolio
- Get news related to markets
- Answer platform questions

**Setup:**
1. Add OpenAI API key to environment:
   ```
   OPENAI_API_KEY=your_openai_api_key
   ```

2. Add Tavily API key for news search:
   ```
   TAVILY_API_KEY=your_tavily_api_key
   ```

**Features:**
- Function calling for real-time market data
- News search integration via Tavily
- Conversation thread persistence
- Guardrails against inappropriate content
- Natural language bet placement

**Example Queries:**
- "What are the odds for market 1?"
- "Bet $50 on YES for Bitcoin market"
- "Show me my bets"
- "Get news about Bitcoin"
- "What markets are available?"

### Static files not showing?
- Verify static files mapping: `/static/` → `/home/yourusername/TVB_Workshops/static/`
- Reload web app

---

## 📈 What's Next?

Post-launch enhancements:
- Email notifications (SendGrid/Mailgun)
- Admin dashboard
- Email verification
- A/B testing
- Google Analytics
- Custom domain

---

## 📄 License

MIT License - Free to use and modify

---

## 🙏 Credits

- Design inspired by [Polymarket](https://polymarket.com)
- Built with Flask, Bootstrap 5, and SQLite
- Deployed on [PythonAnywhere](https://www.pythonanywhere.com)

---

**Your deployment URL**: `https://yourusername.pythonanywhere.com`

**Ready to launch? See [DEPLOY.md](DEPLOY.md)** 🚀
