# Microservices Architecture Documentation

## 🏗️ Architecture Overview

Clean microservices-style architecture with clear separation of concerns.

## 📁 Module Structure

### `/config.py` - Configuration Management
- **Purpose**: Centralized configuration, NO hardcoded secrets
- **Key Features**:
  - Environment variable validation
  - Type-safe configuration
  - Production vs development modes

### `/services/` - Business Logic (Microservices)

#### `blockchain_service.py`
- **Purpose**: Blockchain operations (Sepolia testnet)
- **Features**:
  - Web3 connection management
  - Contract interaction (when ABI available)
  - Transaction signing
- **Dependencies**: web3, eth_account (optional)

#### `chatbot_service.py`
- **Purpose**: AI chatbot with OpenAI function calling
- **Features**:
  - Conversation thread management
  - Function calling orchestration
  - Thread-safe message storage
- **Dependencies**: openai (optional)

#### `chatbot_functions.py`
- **Purpose**: Chatbot function implementations
- **Functions**:
  - `get_all_markets()` - List markets
  - `get_market_odds()` - Get prices
  - `place_bet()` - Queue bet
  - `get_user_bets()` - User portfolio
  - `check_market_status()` - Market resolution
  - `search_news()` - News search
  - `get_market_context()` - Market-related news

#### `market_service.py`
- **Purpose**: Market and LMSR pricing logic
- **Features**:
  - LMSR price calculation
  - Market state management
  - Thread-safe operations
- **Dependencies**: None (pure business logic)

#### `user_service.py`
- **Purpose**: User balance management
- **Features**:
  - Atomic balance operations
  - Auto-credit new users
  - Thread-safe updates
- **Dependencies**: Database utils

#### `bet_service.py`
- **Purpose**: Bet queue processing
- **Features**:
  - Sequential bet processing
  - Result storage with TTL
  - Thread-safe queue
- **Dependencies**: Queue, threading

### `/routes/` - API Endpoints (Blueprints)

#### `api.py` - Main API
- `/api/markets` - Market CRUD
- `/api/markets/<id>/bet` - Place bets
- `/api/markets/<id>/price` - Get prices
- `/api/user/<wallet>/balance` - User balance
- `/api/user/<wallet>/bets` - User bets
- `/api/chat` - Chatbot endpoint
- `/api/admin/markets/blockchain` - Blockchain market creation
- `/api/markets/<id>/blockchain-status` - Blockchain verification

#### `admin.py` - Admin Endpoints
- `/admin/*` - Admin pages
- `/api/markets/<id>/resolve` - Resolve markets
- `/api/markets/<id>/payouts` - Calculate payouts
- `/api/markets/<id>/sell` - Sell shares
- `/api/activity/recent` - Recent activity
- `/api/register` - Email registration
- `/api/count` - Registration count

#### `pages.py` - Page Rendering
- `/` - Homepage
- `/market/<id>` - Market detail
- `/my-bets` - User portfolio
- `/waitlist` - Waitlist page

### `/utils/` - Utilities

#### `database.py`
- **Purpose**: Database connection management
- **Features**:
  - Thread-local connections
  - Context managers for transactions
  - Automatic rollback on errors
  - Connection cleanup

#### `validators.py`
- **Purpose**: Input validation
- **Features**:
  - Wallet address validation
  - Amount validation
  - Email validation
  - Standardized error responses

## 🔄 Request Flow

### Example: Placing a Bet

1. **Frontend** → `POST /api/markets/1/bet`
2. **routes/api.py** → Validates input
3. **services/bet_service.py** → Queues bet
4. **bet_worker()** → Processes sequentially:
   - Checks market status
   - Validates balance (user_service)
   - Calculates shares (market_service)
   - Updates balance (user_service)
   - Stores bet (database)
5. **Frontend** → Polls `/api/bets/<id>/status`

### Example: Chatbot Query

1. **Frontend** → `POST /api/chat`
2. **routes/api.py** → Receives message
3. **services/chatbot_service.py** → Processes with OpenAI
4. **services/chatbot_functions.py** → Executes function calls
5. **Returns** → Natural language response

## 🔒 Security Features

1. **No hardcoded secrets** - All in environment variables
2. **Input validation** - All endpoints validate inputs
3. **SQL injection protection** - Parameterized queries
4. **Thread safety** - Locks on shared resources
5. **CORS** - Configured for cross-origin requests

## 📊 Database Schema

- `markets` - Prediction markets
- `bets` - User bets
- `users` - User balances
- `market_state` - LMSR state (q_yes, q_no)
- `registrations` - Waitlist emails

## 🚀 Deployment

1. Set environment variables
2. Install dependencies: `pip install -r requirements.txt`
3. Initialize database: `python -c "from utils.database import init_db; init_db()"`
4. Deploy contract: `npm run deploy`
5. Run: `python app.py`

## 🔧 Environment Variables Required

```bash
# Required
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
STRIPE_SECRET_KEY=sk_test_...

# Optional (for blockchain)
INFURA_PROJECT_ID=...
SEPOLIA_RPC_URL=https://...
CONTRACT_ADDRESS=0x...
PRIVATE_KEY=...

# Flask
FLASK_ENV=development
SECRET_KEY=...
```

