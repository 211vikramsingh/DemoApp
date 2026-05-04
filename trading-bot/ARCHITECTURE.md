# Trading Bot — Architecture & Security Guide
## Component Relationships, Data Flows & Default Credentials

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Component Map](#2-component-map)
3. [Service-by-Service Breakdown](#3-service-by-service-breakdown)
4. [How Components Communicate](#4-how-components-communicate)
5. [Data Flow: A Trade End-to-End](#5-data-flow-a-trade-end-to-end)
6. [Default Credentials — Complete Reference](#6-default-credentials--complete-reference)
7. [Security Hardening Checklist](#7-security-hardening-checklist)
8. [Environment Variables Reference](#8-environment-variables-reference)

---

## 1. System Overview

The application is a **microservices stack** running inside Docker containers. Every service is isolated and communicates over an internal Docker network. Only nginx is exposed to your browser.

```
Browser (http://localhost)
       │
       ▼
  ┌─────────┐
  │  nginx  │  ← Port 80 (only public-facing port)
  └────┬────┘
       │ routes /api/* → backend
       │ routes /*     → frontend
       ▼
  ┌──────────┐      ┌────────────────┐
  │ frontend │      │    backend     │ ← Port 8000 (internal only)
  │ (React)  │      │   (FastAPI)    │
  └──────────┘      └───┬────────────┘
                        │
              ┌─────────┼──────────┐
              ▼         ▼          ▼
         ┌────────┐ ┌────────┐ ┌────────────────┐
         │Postgres│ │ Redis  │ │ celery_worker  │
         │  +     │ │(cache/ │ │  (background   │
         │Timescale│ │queue) │ │   tasks)       │
         └────────┘ └────────┘ └────────────────┘
```

---

## 2. Component Map

```
trading-bot/
├── docker-compose.yml          ← Defines all 6 services
├── .env                        ← ALL secrets and config (never commit this)
├── start.bat                   ← Windows one-click launcher
│
├── backend/                    ← Python FastAPI application
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py             ← App factory + first-run admin seeding
│       ├── core/
│       │   ├── config.py       ← Reads .env → Settings object
│       │   ├── database.py     ← SQLAlchemy async engine (PostgreSQL)
│       │   ├── security.py     ← JWT tokens, bcrypt password hashing
│       │   ├── risk_manager.py ← Circuit breaker (daily/weekly/monthly halts)
│       │   └── kill_switch.py  ← Emergency stop logic
│       ├── models/             ← Database tables (SQLAlchemy ORM)
│       │   ├── user.py         ← User accounts, roles, TOTP secrets
│       │   ├── strategy.py     ← Trading strategies config
│       │   ├── trade.py        ← Individual trade records
│       │   ├── wallet.py       ← Paper/live wallet balances
│       │   └── audit_log.py    ← Security audit trail
│       ├── schemas/            ← Pydantic request/response models
│       ├── api/
│       │   └── endpoints/
│       │       ├── auth.py     ← Login, token refresh, TOTP
│       │       ├── users.py    ← User CRUD (admin only)
│       │       ├── strategies.py ← Strategy CRUD + backtest
│       │       ├── kill.py     ← Kill switch activate/reset
│       │       └── ws.py       ← WebSocket real-time feed
│       ├── engines/
│       │   ├── signal_engine.py    ← 2:1 R:R signal computation
│       │   ├── greeks_engine.py    ← Black-Scholes Greeks (Delta/Theta/Gamma/Vega)
│       │   ├── kelly_sizer.py      ← Kelly criterion position sizing
│       │   ├── max_pain.py         ← Options max pain calculator
│       │   ├── multi_leg_builder.py ← Multi-leg options strategy builder
│       │   ├── backtesting_engine.py ← Historical strategy testing
│       │   └── paper_trading.py    ← Simulated trade execution
│       ├── brokers/
│       │   ├── base.py         ← Abstract broker interface
│       │   ├── kite_adapter.py ← Zerodha Kite Connect integration
│       │   └── delta_adapter.py ← Delta Exchange integration
│       └── workers/
│           ├── celery_app.py   ← Celery configuration + Redis broker
│           ├── strategy_worker.py ← Runs strategies in background
│           └── data_worker.py  ← Fetches market data, event calendar, funding rates
│
├── frontend/                   ← React TypeScript application
│   ├── Dockerfile
│   ├── src/
│   │   ├── App.tsx             ← Root component + routing
│   │   ├── api/
│   │   │   ├── client.ts       ← Axios HTTP client (baseURL: /api)
│   │   │   └── index.ts        ← Typed API call functions
│   │   ├── stores/
│   │   │   ├── authStore.ts    ← Zustand: JWT token, user info
│   │   │   └── strategyStore.ts ← Zustand: strategies state
│   │   ├── pages/
│   │   │   ├── LoginPage.tsx
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── OptionsPage.tsx
│   │   │   ├── PortfolioPage.tsx
│   │   │   └── AdminPage.tsx
│   │   └── components/
│   │       ├── KillSwitch.tsx       ← Emergency stop button
│   │       ├── StrategyDashboard.tsx ← Strategy list + P&L
│   │       ├── OptionsChainPanel.tsx ← Live options chain + Greeks
│   │       ├── MultiLegBuilder.tsx   ← Options strategy constructor
│   │       ├── PortfolioDashboard.tsx ← Portfolio analytics
│   │       └── AdminPanel.tsx        ← User management
│
└── docker/
    ├── nginx/
    │   └── nginx.conf          ← Reverse proxy rules
    └── postgres/
        └── init.sql            ← Database initialization
```

---

## 3. Service-by-Service Breakdown

### Service 1: nginx (Reverse Proxy)
- **Image**: `nginx:1.25-alpine`
- **Purpose**: Single entry point for all HTTP traffic. Routes requests to the right service.
- **Port exposed**: `80` (the only port the outside world sees)
- **Routing rules**:
  - `GET/POST /api/*` → forwarded to backend:8000 with `/api/` prefix preserved
  - `GET /health` → nginx responds directly (no backend needed)
  - `GET /*` → forwarded to frontend:3000
  - `WS /ws/*` → WebSocket upgrade forwarded to backend
- **Config file**: `docker/nginx/nginx.conf`
- **Credentials used**: None

---

### Service 2: frontend (React UI)
- **Image**: Built from `frontend/Dockerfile` using Node 20
- **Framework**: React 18 + TypeScript + Vite
- **State management**: Zustand
- **Charts**: Recharts
- **Port**: 3000 (internal only — nginx proxies to it)
- **Auth**: Stores JWT token in memory (Zustand store). Token sent as `Authorization: Bearer <token>` header on every API call.
- **Key behaviour**:
  - On login: calls `POST /api/auth/login` → stores returned `access_token`
  - All subsequent API calls include the token
  - If token expires (8-hour default), user is redirected to login
  - WebSocket connection to `ws://localhost/ws/` for real-time updates

---

### Service 3: backend (FastAPI)
- **Image**: Built from `backend/Dockerfile` using Python 3.11
- **Framework**: FastAPI 0.111 + Pydantic v2 + SQLAlchemy 2.0 async
- **Port**: 8000 (internal only — accessed via nginx)
- **On startup**:
  1. Creates all database tables (if they don't exist)
  2. Seeds first-run admin user (if `FIRST_RUN_ADMIN_USERNAME` env var set and no admin exists)
- **Auth mechanism**: JWT tokens (HS256), 8-hour expiry
- **Password storage**: bcrypt-hashed (never stored in plaintext)
- **Broker API secrets**: AES-256 encrypted before database storage using `ENCRYPTION_KEY`
- **Async**: All database and broker calls are non-blocking (asyncpg driver)

---

### Service 4: celery_worker (Background Tasks)
- **Image**: Same Docker image as backend (same `requirements.txt`)
- **Framework**: Celery 5.4 + Redis as message broker
- **What it runs**:
  - `strategy_worker.py` — polls strategies, generates signals, executes trades
  - `data_worker.py` — fetches market data, event calendar (NSE corporate actions), funding rates (Delta Exchange)
- **Queue priority**: `kill_queue` has higher priority than `default` — Kill Switch commands are always processed first
- **No port exposed** — only communicates via Redis and PostgreSQL

---

### Service 5: postgres (Database)
- **Image**: `timescale/timescaledb:latest-pg16`
- **Purpose**: Persistent storage for all application data
- **TimescaleDB**: Extension for efficient time-series data (trade history, OHLCV data)
- **Port**: 5432 (internal only — not exposed to host by default in production)
- **Tables**:
  - `users` — user accounts
  - `strategies` — strategy configurations
  - `trades` — trade records (entry/exit/P&L)
  - `wallets` — paper and live wallet balances
  - `audit_logs` — security events (login, kill switch, admin actions)
- **Volume**: `postgres_data` (persists across restarts)

---

### Service 6: redis (Cache & Message Queue)
- **Image**: `redis:7.2-alpine`
- **Two roles**:
  1. **Celery broker**: Celery workers receive task messages via Redis queues
  2. **Circuit breaker state**: Daily SL count, halt flags stored as Redis keys (namespaced by user ID and date)
- **Port**: 6379 (internal only)
- **Volume**: `redis_data` (persists across restarts)
- **Key naming pattern**: `cb:daily_sl:{user_id}:{date}`, `cb:kill_halt:{user_id}`, etc.

---

## 4. How Components Communicate

```
┌─────────────────────────────────────────────────────────────────┐
│                    BROWSER SESSION                              │
│                                                                  │
│  User logs in → JWT token stored in Zustand (memory only)       │
│  Every API call adds: Authorization: Bearer <token>             │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTPS (HTTP in dev)
                               ▼
                         ┌──────────┐
                         │  nginx   │
                         └────┬─────┘
              /api/*          │         /*
         ┌────────────────────┤     ┌───────────┐
         ▼                    │     ▼           │
   ┌──────────┐               │ ┌──────────┐   │
   │ backend  │◄──────────────┘ │ frontend │   │
   │ FastAPI  │                 └──────────┘   │
   └────┬─────┘                                │
        │                                      │
   ┌────┼──────────────────┐                   │
   │    │    │              │                   │
   ▼    ▼    ▼              ▼                   │
┌──────┐ ┌────────┐  ┌───────────────┐         │
│Redis │ │Postgres│  │ Broker APIs   │         │
└───┬──┘ └────────┘  │ (Kite/Delta) │         │
    │                └───────────────┘         │
    │ Celery tasks                              │
    ▼                                          │
┌────────────────┐                             │
│ celery_worker  │                             │
│                │◄────────────────────────────┘
│ • strategy loop│   WebSocket pushes to frontend
│ • data fetcher │
└────────────────┘
```

### Communication protocols

| From → To | Protocol | What's sent |
|---|---|---|
| Browser → nginx | HTTP/WebSocket | All user requests |
| nginx → backend | HTTP proxy | REST API calls |
| nginx → frontend | HTTP proxy | Page and asset requests |
| backend → PostgreSQL | asyncpg (TCP) | SQL queries |
| backend → Redis | redis-py async (TCP) | Cache reads/writes, task publishing |
| celery_worker → Redis | redis-py (TCP) | Task consumption |
| celery_worker → PostgreSQL | asyncpg (TCP) | Trade writes |
| celery_worker → Kite API | HTTPS | Order placement, market data |
| celery_worker → Delta API | HTTPS | Crypto order placement |
| backend → frontend | WebSocket | Real-time price/P&L updates |

---

## 5. Data Flow: A Trade End-to-End

Here is exactly what happens from strategy creation to trade execution:

```
1. USER creates strategy (frontend)
        │
        ▼
2. POST /api/strategies → backend saves to PostgreSQL
        │
        ▼
3. celery_worker picks up the strategy (polls every N seconds)
        │
        ▼
4. data_worker fetches OHLCV data from Kite/Delta API
        │
        ▼
5. signal_engine.compute_signal() called:
   - Finds S/R levels from price history
   - Computes SL = min(S/R distance, 1% capital)
   - Validates R:R ≥ 2.0
   - Returns TradeSignal or None
        │
        ▼
6. kelly_sizer.get_position_size() called:
   - Computes optimal lot size (Kelly/half-Kelly/fixed)
   - Applies hard caps (5% single trade, 20% per instrument)
        │
        ▼
7. risk_manager.CircuitBreaker.is_halted() called:
   - Checks Redis for daily SL count, weekly/monthly drawdown
   - Returns halt reason if applicable
        │
   ┌────┴────────────────────────────────────────┐
   │ HALTED?                                      │
   │ Yes → log audit event, notify Telegram       │
   │ No  → continue                               │
   └────┬────────────────────────────────────────┘
        │
        ▼
8. Wallet type check:
   - paper → paper_trading.simulate_order() → write to DB
   - real  → broker.place_order() → Kite/Delta API → write to DB
        │
        ▼
9. WebSocket pushes trade notification to browser
        │
        ▼
10. If SL hit → risk_manager.record_sl_hit():
    - Increments Redis daily SL counter
    - If counter reaches 3 → sets halt flag → all strategies stop
        │
        ▼
11. Telegram notification sent (if configured)
```

---

## 6. Default Credentials — Complete Reference

> ⚠️ **All defaults below MUST be changed before using the app with real money or on a shared network.**

### 6.1 Application Admin User

| What | Default Value | Where Set | Where Used |
|---|---|---|---|
| Admin username | `admin` | `.env` → `FIRST_RUN_ADMIN_USERNAME` | Login page |
| Admin password | `changeme_strong_password` | `.env` → `FIRST_RUN_ADMIN_PASSWORD` | Login page |

**How to change:**
1. Stop the app: `docker compose down -v` (the `-v` clears the DB so the new password takes effect)
2. Edit `.env`:
   ```
   FIRST_RUN_ADMIN_USERNAME=your_username
   FIRST_RUN_ADMIN_PASSWORD=YourStr0ng!Password
   ```
3. Restart: `docker compose up -d`

Alternatively (without data loss), change it via the Admin panel after login:
**Admin → Users → Edit → New Password → Save**

---

### 6.2 Database Credentials

| What | Default Value | Where Set | Where Used |
|---|---|---|---|
| DB username | `tradingbot` | `.env` → `DB_USER` | PostgreSQL + backend connection string |
| DB password | `changeme` | `.env` → `DB_PASSWORD` | PostgreSQL + backend connection string |
| DB name | `tradingbot` | `.env` → `DB_NAME` | PostgreSQL + backend |

**Where the password appears in config:**
```
# .env
DB_USER=tradingbot
DB_PASSWORD=changeme          ← change this
DB_NAME=tradingbot

# Automatically used in docker-compose.yml:
DATABASE_URL: postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@postgres:5432/${DB_NAME}
```

**How to change:**
```
# .env
DB_PASSWORD=MyStr0ngDBPass!

# Then full restart (volume must be reset OR use pg_password update):
docker compose down -v
docker compose up -d
```

---

### 6.3 JWT Secret Key

| What | Default Value | Where Set | Where Used |
|---|---|---|---|
| JWT Secret | `CHANGE_ME_IN_PRODUCTION` (fallback in code) | `.env` → `SECRET_KEY` | Signs all user tokens |

> If `SECRET_KEY` is predictable, an attacker can forge login tokens for any user.

**How to change:**
```powershell
# Generate a cryptographically random key:
python -c "import secrets; print(secrets.token_hex(32))"
```
Paste the output into `.env` as `SECRET_KEY=<output>`.
All existing user sessions will be invalidated (users must log in again).

---

### 6.4 Encryption Key (Broker API Secrets)

| What | Default Value | Where Set | Where Used |
|---|---|---|---|
| AES-256 key | `CHANGE_ME_32_BYTE_HEX` (fallback) | `.env` → `ENCRYPTION_KEY` | Encrypts Kite/Delta API keys stored in DB |

> Broker API keys are stored encrypted. If this key is leaked, your broker keys can be decrypted.

**How to change:**
```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```
Paste into `.env` as `ENCRYPTION_KEY=<output>`.
⚠️ If you change this after broker keys are stored, they must be re-entered (the old encrypted values cannot be decrypted with the new key).

---

### 6.5 Broker API Keys

| What | Default Value | Where Set | Where Used |
|---|---|---|---|
| Kite API Key | `your_kite_api_key` | `.env` → `KITE_API_KEY` | Zerodha live trading |
| Kite API Secret | `your_kite_api_secret` | `.env` → `KITE_API_SECRET` | Zerodha live trading |
| Delta API Key | `your_delta_api_key` | `.env` → `DELTA_API_KEY` | Delta Exchange live trading |
| Delta API Secret | `your_delta_api_secret` | `.env` → `DELTA_API_SECRET` | Delta Exchange live trading |

These are placeholders only. Paper trading works without them.

---

### 6.6 Where `.env` Values Flow

```
.env file
    │
    ├── SECRET_KEY ──────────────────► backend/app/core/security.py
    │                                    (JWT signing/verification)
    │
    ├── ENCRYPTION_KEY ──────────────► backend/app/core/security.py
    │                                    (AES-256 encrypt broker secrets)
    │
    ├── DB_USER / DB_PASSWORD ───────► docker-compose.yml
    │                                    → postgres service (env vars)
    │                                    → backend DATABASE_URL
    │
    ├── REDIS_URL ───────────────────► backend/app/workers/celery_app.py
    │                                    (Celery broker URL)
    │
    ├── KITE_API_KEY / SECRET ───────► backend/app/brokers/kite_adapter.py
    │
    ├── DELTA_API_KEY / SECRET ──────► backend/app/brokers/delta_adapter.py
    │
    ├── TELEGRAM_BOT_TOKEN ──────────► backend/app/workers/strategy_worker.py
    │
    ├── FIRST_RUN_ADMIN_USERNAME ────► backend/app/main.py → _seed_admin()
    └── FIRST_RUN_ADMIN_PASSWORD ────► (hashed with bcrypt before storage)
```

---

## 7. Security Hardening Checklist

Use this checklist before going live or sharing the app.

### Credentials (Critical)
- [ ] Change `FIRST_RUN_ADMIN_PASSWORD` from `changeme_strong_password` to a strong unique password
- [ ] Change `DB_PASSWORD` from `changeme` to a strong unique password
- [ ] Generate a random `SECRET_KEY` (64 hex chars) — never use the default
- [ ] Generate a random `ENCRYPTION_KEY` (64 hex chars) — never use the default
- [ ] Set real broker API keys (Kite/Delta) — never leave as `your_*_api_key`

### Access Control
- [ ] Enable TOTP 2FA for the admin account (`POST /api/auth/totp/setup`)
- [ ] Create per-user accounts — never share the admin credentials with traders
- [ ] Assign `role: user` to traders (not `admin`)
- [ ] Regularly review the audit log (`GET /api/audit-logs`) for unusual activity

### Network
- [ ] If exposing to the internet: put nginx behind HTTPS (add an SSL certificate)
- [ ] Change PostgreSQL port in `docker-compose.yml` — remove the `5432:5432` port mapping (it doesn't need to be accessible from outside Docker)
- [ ] Change Redis port mapping — remove `6379:6379` from `docker-compose.yml`
- [ ] Use a firewall to restrict port 80 to known IP addresses if possible

### File Security
- [ ] Add `.env` to `.gitignore` (already done — **never commit `.env` to git**)
- [ ] Keep `.env` file permissions restricted: `icacls .env /inheritance:r /grant:r "%USERNAME%:F"`
- [ ] Back up `.env` securely (encrypted) — losing `ENCRYPTION_KEY` means losing access to stored broker keys

### Monitoring
- [ ] Set up Telegram alerts so you're notified of all trades and halts
- [ ] Review Portfolio dashboard daily
- [ ] Check circuit breaker status if trading stops unexpectedly

---

## 8. Environment Variables Reference

Complete list of all variables in `.env` with descriptions:

| Variable | Required | Default in Code | Purpose |
|---|---|---|---|
| `DB_USER` | Yes | `tradingbot` | PostgreSQL username |
| `DB_PASSWORD` | Yes | `tradingbot` | PostgreSQL password — **change this** |
| `DB_NAME` | Yes | `tradingbot` | PostgreSQL database name |
| `SECRET_KEY` | Yes | `CHANGE_ME_IN_PRODUCTION` | JWT token signing key — **change this** |
| `ENCRYPTION_KEY` | Yes | `CHANGE_ME_32_BYTE_HEX` | AES-256 key for broker secrets — **change this** |
| `DEBUG` | No | `false` | Enable debug logging (set `false` in production) |
| `KITE_API_KEY` | For live NSE | empty | Zerodha Kite API key |
| `KITE_API_SECRET` | For live NSE | empty | Zerodha Kite API secret |
| `DELTA_API_KEY` | For live crypto | empty | Delta Exchange API key |
| `DELTA_API_SECRET` | For live crypto | empty | Delta Exchange API secret |
| `DELTA_BASE_URL` | No | `https://api.delta.exchange` | Delta Exchange API URL |
| `TELEGRAM_BOT_TOKEN` | No | empty | Telegram notifications |
| `FIRST_RUN_ADMIN_USERNAME` | Yes (first run) | empty | Admin login username — **change this** |
| `FIRST_RUN_ADMIN_PASSWORD` | Yes (first run) | empty | Admin login password — **change this** |

### Risk parameters (optional overrides)

| Variable | Default | Meaning |
|---|---|---|
| `MAX_SINGLE_TRADE_PCT` | `0.05` | Max 5% of portfolio per trade |
| `MAX_INSTRUMENT_PCT` | `0.20` | Max 20% of portfolio per instrument |
| `DAILY_SL_LIMIT` | `3` | Halt after 3 stop-losses in one day |
| `WEEKLY_DRAWDOWN_PCT` | `0.08` | Halt if 8% rolling 5-day drawdown |
| `MONTHLY_DRAWDOWN_PCT` | `0.15` | Halt if 15% calendar-month drawdown |
