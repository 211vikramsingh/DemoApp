# Trading Bot — How-To Guide
## Step-by-Step Instructions for Every Feature

---

## Table of Contents

1. [Logging In & Out](#1-logging-in--out)
2. [Dashboard Overview](#2-dashboard-overview)
3. [Creating & Managing Strategies](#3-creating--managing-strategies)
4. [Running Paper Trading (Simulated)](#4-running-paper-trading-simulated)
5. [Switching to Live Trading](#5-switching-to-live-trading)
6. [Options Chain & Greeks](#6-options-chain--greeks)
7. [Multi-Leg Options Builder](#7-multi-leg-options-builder)
8. [Understanding Trade Signals & R:R](#8-understanding-trade-signals--rr)
9. [Kill Switch — Emergency Stop](#9-kill-switch--emergency-stop)
10. [Risk Management & Circuit Breakers](#10-risk-management--circuit-breakers)
11. [Portfolio Dashboard](#11-portfolio-dashboard)
12. [Admin Panel — User Management](#12-admin-panel--user-management)
13. [Backtesting a Strategy](#13-backtesting-a-strategy)
14. [Broker API Setup (Zerodha & Delta Exchange)](#14-broker-api-setup-zerodha--delta-exchange)
15. [Telegram Notifications](#15-telegram-notifications)
16. [Using the Swagger API Docs](#16-using-the-swagger-api-docs)

---

## 1. Logging In & Out

### Login
1. Open http://localhost in your browser
2. Enter your **Username** and **Password**
3. Click **Login**

> Default credentials (change these — see [Security Guide](ARCHITECTURE.md)):
> - Username: `admin`
> - Password: `changeme_strong_password`

### TOTP Two-Factor Authentication (optional)
If you've enabled TOTP:
1. After entering username/password, a **TOTP code** field appears
2. Open your authenticator app (Google Authenticator, Authy, etc.)
3. Enter the 6-digit code

### To set up TOTP
Go to **API Docs** → `POST /api/auth/totp/setup` → click **Try it out** → **Execute**
Scan the returned QR code with your authenticator app.

### Logout
Click your username in the top-right corner → **Logout**
Your session token is cleared from the browser.

---

## 2. Dashboard Overview

After login you land on the **Strategy Dashboard** which shows:

| Panel | What it shows |
|---|---|
| **Active Strategies** | All running strategies with P&L, status, mode |
| **Portfolio Summary** | Total capital, deployed, available, overall P&L |
| **Recent Signals** | Last 20 buy/sell signals generated |
| **Kill Switch** | One-click emergency halt button |

Navigation tabs:
- **Dashboard** — strategy overview
- **Options** — options chain and Greeks
- **Portfolio** — detailed P&L and trade history
- **Admin** — user and system management (admin role only)

---

## 3. Creating & Managing Strategies

### Create a Strategy

1. On the Dashboard, click **+ New Strategy**
2. Fill in the form:

| Field | Description | Example |
|---|---|---|
| **Name** | Descriptive name | `Nifty Iron Condor` |
| **Instruments** | Comma-separated symbols | `NIFTY, BANKNIFTY` |
| **Automation Mode** | How trades are executed | `semi_auto` |
| **Wallet Type** | Paper (simulated) or Real money | `paper` |
| **Position Sizing** | Kelly / Half-Kelly / Fixed % | `half_kelly` |
| **Win Rate %** | Your historical win rate (for Kelly) | `60` |
| **Max Capital %** | Max % of portfolio per trade | `5` |

3. Click **Create Strategy**

### Automation Modes

| Mode | What happens |
|---|---|
| `manual` | Signals shown as alerts only — you click to execute each trade |
| `semi_auto` | Bot places the entry order; you confirm SL and target |
| `auto` | Bot executes entry, SL, and target orders fully automatically |

> **Recommendation for beginners**: Start with `manual` or `semi_auto` and `wallet_type: paper`

### Edit a Strategy
1. Click the strategy name on the Dashboard
2. Click **Edit**
3. Modify fields and click **Save**

### Pause / Resume a Strategy
- Click the **⏸ Pause** button next to a strategy to stop signal generation
- Click **▶ Resume** to restart it

### Delete a Strategy
1. Open the strategy
2. Click **Delete** → confirm the prompt

---

## 4. Running Paper Trading (Simulated)

Paper trading uses **virtual money** — no real orders are placed. Perfect for testing.

### How to enable
When creating a strategy, set **Wallet Type** to `paper`.

### How it works
- The bot generates real signals based on live market data
- Trades are simulated: entries, exits, P&L tracked in the database
- **Commission modeled** — a 0.05% commission is deducted on every open and close leg, so paper results match realistic live trading costs
- All risk rules (SL, 3-SL daily limit, Kill Switch) apply identically
- You see real-time P&L as if trading with real money

### Switching paper → live
1. Edit the strategy
2. Change **Wallet Type** from `paper` to `real`
3. Ensure your broker API keys are configured (see [Section 14](#14-broker-api-setup-zerodha--delta-exchange))
4. Click **Save**

---

## 5. Switching to Live Trading

### Prerequisites
- Zerodha account with Kite Connect API access (Indian markets)
- OR Delta Exchange account with API keys (Bitcoin/crypto)
- Broker API keys entered in `.env` or Admin panel

### Steps
1. Go to **Admin → Broker Settings**
2. Enter your Kite API key and secret (or Delta Exchange key and secret)
3. Click **Save & Test** — a green tick means connection successful
4. Edit your strategy → set **Wallet Type** to `real`
5. Set **Automation Mode** to your preference

> ⚠️ **Always test with paper trading first.** Run the same strategy in paper mode for at least 5–10 trading sessions before switching to live.

---

## 6. Options Chain & Greeks

Navigate to the **Options** tab.

### Viewing the Options Chain
1. Select the **Underlying** (e.g., NIFTY, BANKNIFTY, SENSEX, BTC)
2. Select the **Expiry date** from the dropdown
3. The chain shows all strikes with:

| Column | Meaning |
|---|---|
| **Strike** | Option strike price |
| **Call LTP** | Last traded price of the call |
| **Call OI** | Open interest for the call |
| **Call Delta** | Delta (0 to 1) — how much price moves per ₹1 in underlying |
| **Call Theta** | Daily time decay in ₹ per lot |
| **Call Gamma** | Rate of change of Delta |
| **Call Vega** | P&L impact per 1% change in IV |
| **Put LTP/OI/Greeks** | Same for puts |

### Understanding the Greeks

**Delta (Δ)**
- Call delta: 0 to +1 (ITM calls closer to 1)
- Put delta: -1 to 0
- Example: Delta 0.5 → option moves ₹0.50 for every ₹1 move in the underlying

**Theta (Θ)**
- Always negative for buyers (time decay hurts buyers)
- Positive for sellers (time decay helps sellers)
- Example: Theta -2.5 → option loses ₹2.50 per day just from time passing

**Gamma (Γ)**
- High gamma = Delta changes rapidly (near expiry, ATM options)
- Gamma blast: when ATM options near expiry experience explosive Delta acceleration

**Vega (ν)**
- Sensitivity to Implied Volatility (IV)
- Example: Vega 15 → option gains ₹15 per 1% increase in IV

### Max Pain
The options chain panel also shows **Max Pain** — the strike price where option sellers (exchanges/operators) suffer minimum loss. This is often used as a magnet price on expiry day.

---

## 7. Multi-Leg Options Builder

Go to **Options → Multi-Leg Builder**.

This lets you construct complex options strategies (spreads, Iron Condors, straddles, etc.) and see the combined Greeks and P&L profile before placing.

### Build an Iron Condor (Example)

1. Click **+ Add Leg**
2. Add 4 legs:

| Leg | Action | Type | Strike |
|---|---|---|---|
| 1 | Sell | Call | ATM + 100 |
| 2 | Buy | Call | ATM + 200 |
| 3 | Sell | Put | ATM - 100 |
| 4 | Buy | Put | ATM - 200 |

3. The builder shows:
   - **Net Premium** received/paid
   - **Max Profit** (premium received)
   - **Max Loss** (spread width − premium)
   - **Breakeven points** (upper and lower)
   - **Combined Delta, Theta, Vega, Gamma**

4. Click **Place Strategy** to send all legs as orders (in live mode) or record them (paper mode)

### Available strategy templates
Click **Load Template** to get pre-built configurations for:
- Iron Condor
- Iron Butterfly
- Bull Call Spread
- Bear Put Spread
- Straddle / Strangle
- Calendar Spread

---

## 8. Understanding Trade Signals & R:R

The bot enforces a **minimum 2:1 Reward-to-Risk ratio** on every signal.

### How a signal is calculated

1. **Entry price** — current market price or limit price
2. **Stop Loss** — tightest of:
   - Distance to the nearest Support/Resistance level
   - 1% of the capital allocated to this trade
3. **Target** — entry ± (2 × SL distance) minimum

### Reading a signal

| Field | Meaning |
|---|---|
| **Direction** | Long (buy) or Short (sell) |
| **Entry** | Price to enter at |
| **Stop Loss** | Exit immediately if price hits this |
| **Target** | Take profit at this level |
| **R:R** | Reward:Risk ratio (always ≥ 2.0) |
| **Capital at Risk** | ₹ amount risked on this trade |

### Example
- Nifty at 22,500
- Nearest support: 22,350 (distance: 150 points)
- 1% of ₹1,00,000 capital = ₹1,000 → per unit SL = ₹1,000 / 50 (lot size) = 20 points
- **SL = 20 points** (tighter stop wins — 20 < 150)
- **Target = 22,540** (entry + 2 × 20 = 22,540)
- **R:R = 2:1** ✓

---

## 9. Kill Switch — Emergency Stop

The Kill Switch is a **hard stop** that immediately halts ALL trading activity.

### Activate the Kill Switch
1. Click the red **🔴 Kill Switch** button (always visible on the Dashboard)
2. Confirm the prompt
3. **All automated strategies stop immediately**
4. No new orders are placed
5. Open positions are NOT automatically closed (you must exit them manually)

### What happens after activation
- Strategy status changes to `HALTED`
- The Kill Switch remains active until manually reset
- A halt record is written to the audit log

### Resetting the Kill Switch (Admin only)
1. Go to **Admin → System**
2. Click **Reset Kill Switch**
3. Confirm the reset
4. Strategies resume only after you manually re-activate them

### API alternative
```
POST /api/kill/activate    — activate kill switch
POST /api/kill/reset       — reset (admin only)
GET  /api/kill/status      — check current status
```

---

## 10. Risk Management & Circuit Breakers

The bot enforces three automatic risk limits that trigger automatic halts.

### Daily Stop-Loss Limit (default: 3 SL hits)
- After **3 stop-losses in a single day**, all trading halts for that day
- Default limit is **3**; admins can change this via `DAILY_SL_LIMIT` in `.env`
- Resets automatically at midnight (next trading day)
- **Cannot be overridden by users** — only admins can reset early

### Weekly Drawdown (default: 8%)
- If your portfolio loses **8% over any rolling 5-trading-day period**, trading halts for the rest of the week
- Default threshold is **8%**; admins can change this via `WEEKLY_DRAWDOWN_PCT` in `.env`
- Resets automatically at the start of the next trading week (Monday)

### Monthly Drawdown (default: 15%)
- If your portfolio loses **15% in a calendar month**, trading halts for the rest of that month
- Default threshold is **15%**; admins can change this via `MONTHLY_DRAWDOWN_PCT` in `.env`
- Requires **admin manual reset** to re-enable early

### What to do when halted
1. Check the Dashboard for the halt reason shown in the alert bar
2. Review recent trades in **Portfolio → Trade History**
3. Identify what went wrong
4. Wait for the automatic reset, OR ask your admin to reset early

### Position Sizing (Kelly Criterion)

| Method | What it does |
|---|---|
| `kelly` | Full Kelly — sizes position based on edge and win rate |
| `half_kelly` | Half Kelly — safer, uses 50% of Kelly recommendation |
| `fixed` | Fixed % of portfolio per trade (e.g., 5%) |

**Kelly formula**: `f = (win_rate × rr_ratio - (1 - win_rate)) / rr_ratio`

Hard caps applied on top of Kelly:
- Max 5% of portfolio per single trade
- Max 20% of portfolio in any one instrument

---

## 11. Portfolio Dashboard

Navigate to the **Portfolio** tab.

### What you see

| Section | Content |
|---|---|
| **Summary Cards** | Total capital, P&L today, P&L this month, Win rate |
| **Equity Curve** | Chart of portfolio value over time |
| **Trade History** | All executed trades with entry/exit/P&L |
| **Open Positions** | Currently open trades |
| **Strategy Breakdown** | P&L per strategy |

### Filters
- **Date range** — filter trades by date
- **Strategy** — show only one strategy
- **Instrument** — filter by stock/index/option
- **Status** — open / closed / stopped-out

### Export
Click **Export CSV** to download trade history for analysis in Excel.

---

## 12. Admin Panel — User Management

Only users with the `admin` role can access this panel.

Navigate to **Admin** tab.

### Add a New User
1. Click **+ New User**
2. Enter:
   - **Username** (must be unique)
   - **Email**
   - **Password** (minimum 8 characters)
   - **Role**: `user` or `admin`
3. Click **Create**

### Change a User's Password
1. Find the user in the list
2. Click **Edit**
3. Enter new password in the **Password** field
4. Click **Save**

### Deactivate a User
- Click **Deactivate** next to a user — they cannot log in but their data is preserved
- Click **Activate** to restore access

### User Roles

| Role | Permissions |
|---|---|
| `user` | Create strategies, paper/live trade, view own portfolio |
| `admin` | All user permissions + manage users, reset kill switch, reset circuit breakers |

### Support for 5+ Users
Each user has their own:
- Isolated strategies (users cannot see other users' strategies)
- Separate circuit breaker counters (one user's SL hits don't affect others)
- Independent portfolio tracking
- Personal TOTP 2FA settings

---

## 13. Backtesting a Strategy

Backtesting lets you test a strategy on **historical data** before trading live.

### Via the API (Swagger UI)

1. Go to http://localhost/api/docs
2. Click **Authorize** → enter your token
3. Navigate to the **backtesting** section
4. Use `POST /api/strategies/{id}/backtest` with parameters:

```json
{
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "initial_capital": 1000000,
  "strategy_type": "ema_cross",
  "commission_pct": 0.0005
}
```

**Available strategy types:**

| `strategy_type` | Algorithm |
|---|---|
| `ema_cross` | EMA crossover (default) — fast EMA crosses above/below slow EMA |
| `rsi` | RSI mean-reversion — buy oversold, sell overbought |
| `breakout` | Donchian channel breakout — enter on N-period high/low break |
| `custom` | Inject your own `bt.Strategy` subclass via the API |

5. The response includes:
   - Total return %
   - Max drawdown
   - Sharpe ratio
   - Win rate
   - Total trades executed

### Interpreting results

| Metric | Good | Warning |
|---|---|---|
| **Win Rate** | > 50% | < 40% |
| **R:R Ratio** | ≥ 2.0 | < 1.5 |
| **Max Drawdown** | < 10% | > 20% |
| **Sharpe Ratio** | > 1.0 | < 0.5 |

---

## 14. Broker API Setup (Zerodha & Delta Exchange)

### Zerodha Kite Connect (Indian Markets)

**What you need:**
1. A Zerodha trading account (https://zerodha.com)
2. Kite Connect subscription (~₹2,000/month) at https://developers.kite.trade/
3. Create an app → get `api_key` and `api_secret`

**Configure in `.env`:**
```
KITE_API_KEY=your_api_key_here
KITE_API_SECRET=your_api_secret_here
```
Restart the application: `docker compose restart backend celery_worker`

**Markets supported via Kite:**
- Nifty 50 options & futures
- BankNifty options & futures
- Sensex (via BSE)
- Individual equity F&O

### Delta Exchange (Bitcoin & Crypto)

**What you need:**
1. A Delta Exchange account (https://www.delta.exchange)
2. Go to Account → API Keys → Create Key
3. Copy the `api_key` and `api_secret`

**Configure in `.env`:**
```
DELTA_API_KEY=your_key_here
DELTA_API_SECRET=your_secret_here
```

**Markets supported via Delta:**
- Bitcoin perpetual and options
- Ethereum perpetual
- Other crypto derivatives

---

## 15. Telegram Notifications

Get trade alerts and halt notifications sent to your Telegram.

### Setup

1. Open Telegram → search for **@BotFather**
2. Send `/newbot` → follow prompts → copy the **token**
3. Add to `.env`:
   ```
   TELEGRAM_BOT_TOKEN=1234567890:ABCDEF...
   ```
4. Restart: `docker compose restart celery_worker`
5. Send `/start` to your bot in Telegram to activate it

### What you receive
- ✅ Trade entry notification
- 🎯 Target hit notification
- 🛑 Stop-loss hit notification
- ⚠️ Circuit breaker activated
- 🔴 Kill Switch activated

---

## 16. Using the Swagger API Docs

The API docs at http://localhost/api/docs let you interact with every endpoint directly.

### Authenticate
1. Go to http://localhost/api/docs
2. Click the **Authorize 🔓** button (top right)
3. In the `bearerAuth` field, enter: `your_access_token`
   - Get a token: `POST /api/auth/login` with username/password → copy `access_token`
4. Click **Authorize** → **Close**

### Try an endpoint
1. Click any endpoint (e.g., `GET /api/strategies`)
2. Click **Try it out**
3. Fill in any required parameters
4. Click **Execute**
5. View the response in the **Response body** section

### Key endpoints

| Endpoint | Method | What it does |
|---|---|---|
| `/api/auth/login` | POST | Login, get JWT token |
| `/api/strategies` | GET | List all your strategies |
| `/api/strategies` | POST | Create a new strategy |
| `/api/strategies/{id}` | GET | Get strategy details |
| `/api/kill/activate` | POST | Activate Kill Switch |
| `/api/kill/status` | GET | Check Kill Switch status |
| `/api/users` | GET | List users (admin only) |
| `/health` | GET | Service health check |
