# Plan: Autonomous Trading Bot — Nifty / BankNifty / Sensex / Equities / Bitcoin (Delta Exchange)

**Date:** May 4, 2026  
**Status:** Approved — All gaps mitigated (Tax Audit Trail excluded per decision)

---

## TL;DR

Build a full-stack autonomous trading bot application supporting Indian markets (Nifty, Bank Nifty, Sensex, equities) and crypto derivatives (Bitcoin/ETH via Delta Exchange). React + TypeScript frontend (Vite) with a Python FastAPI backend. Portable via Docker Compose with automatic dependency check on launch. Per-strategy configurable automation: fully automatic or semi-automatic (30s approval window) for real trades.

**Multi-stock confirmed:** The bot trades multiple instruments simultaneously — Nifty50, BankNifty, Sensex index, individual NSE equities (configurable watchlist), and Delta Exchange crypto instruments — each running independent strategy workers in parallel. Each user can follow and trade a different set of instruments on their own personalised dashboards.

**Kill Switch included:** Trader can issue a Kill Switch command at any time — globally (all positions, all strategies) or per-instrument / per-trade — via dashboard button, keyboard shortcut, or direct command to the bot API. All open orders are cancelled and all positions are market-squared-off within one tick.

---

## Decisions Made

| Decision | Choice |
|---|---|
| Broker | Zerodha Kite Connect (₹2000/month API) |
| Deployment | Docker Compose web app (browser-based, portable) |
| Crypto Exchange | Delta Exchange (BTC/ETH futures, options, perpetuals) |
| Real Trade Automation | Configurable per strategy — fully auto OR semi-auto (30s approval) |

---

## Gap Analysis — All Gaps & Mitigations

| Gap | Status | Mitigated In |
|---|---|---|
| Broker API | ✅ Zerodha Kite Connect | Phase 1 |
| Options Chain (OI, PCR, Max Pain) | ✅ Mitigated | Phase 2 (feed) + Phase 3 (Max Pain engine) + Phase 4 (PCR signal) |
| India VIX | ✅ Mitigated | Phase 2 (feed) + Phase 4 (VIX-based position sizer) |
| Multi-Timeframe Confluence | ✅ Mitigated | Phase 3 (MTF confluence scorer, entry gate ≥70) |
| News & Economic Event Calendar | ✅ Mitigated | Phase 2 step 13 — NSE/RBI ingestion + 30min signal blackout |
| Position Sizing (Kelly Criterion) | ✅ Mitigated | Phase 4 step 26 — `f* = (bp−q)/b`, half-Kelly, VIX multiplier |
| Market Holiday Calendar | ✅ Mitigated | Phase 2 step 12 |
| Tax Audit Trail | ❌ EXCLUDED | Out of scope per user decision |
| 2FA + Encrypted API Key Vault | ✅ Mitigated | Phase 1 (pyotp + AES-256) |
| Weekly + Monthly Circuit Breaker | ✅ Mitigated | Phase 4 steps 30–31 (8% weekly / 15% monthly) |
| Multi-leg Options Strategies | ✅ Mitigated | Phase 5 step 37 (Bull Spread, Bear Spread, Iron Condor, Straddle, Strangle) |
| Delta Exchange IV Skew / Crypto Greeks | ✅ Mitigated | Phase 3 step 21 — crypto Greeks engine, 25-delta risk reversal |
| Funding Rate (Delta Exchange perps) | ✅ Mitigated | Phase 2 step 14 (feed) + Phase 4 step 28 (carry filter) |
| Slippage & Execution Quality tracking | ✅ Mitigated | Phase 6 step 44 |
| Walk-forward + Monte Carlo backtesting | ✅ Mitigated | Phase 5 step 34 |
| Correlation Dashboard (Nifty/BNF/BTC) | ✅ Mitigated | Phase 7 step 48 |
| Kill Switch (global + per-trade/instrument) | ✅ Mitigated | Phase 4 step 33 + Phase 6 step 45 + Phase 8 step 56 |
| Multi-stock simultaneous trading | ✅ Confirmed | Architecture + Phase 5 step 36 (per-instrument Celery workers) |

---

## Architecture

```
┌───────────────────────────────────────────────────────────────┐
│  Docker Compose (portable — single command launch)           │
│                                                               │
│  ┌─────────────────┐   ┌────────────────────────────────┐   │
│  │  Nginx (80/443) │──▶│  React + TS Frontend (Vite)    │   │
│  └────────┬────────┘   └────────────────────────────────┘   │
│           │REST+WS      ┌────────────────────────────────┐   │
│           └────────────▶│  Python FastAPI Backend        │   │
│                         │  - Signal Engine               │   │
│                         │  - Backtesting Engine          │   │
│                         │  - Broker Adapter Layer        │   │
│                         │  - Options Greeks Engine       │   │
│                         │  - Max Pain Engine             │   │
│                         │  - Kelly Criterion Sizer       │   │
│                         │  - Multi-leg Order Builder     │   │
│                         │  - Event Calendar / Blackout   │   │
│                         └────────┬───────────────────────┘   │
│                                  │                            │
│  ┌──────────────┐  ┌─────────┐  ┌────────────────────────┐  │
│  │ PostgreSQL + │  │  Redis  │  │ Celery Workers          │  │
│  │ TimescaleDB  │  │(cache / │  │ (signal gen, data       │  │
│  │(OHLCV, OI,  │  │ queue)  │  │  ingest, order exec,    │  │
│  │trades, etc) │  └─────────┘  │  circuit breaker)       │  │
│  └──────────────┘               └────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
        │                                │
   Zerodha Kite Connect           Delta Exchange API
   (Nifty, BankNifty,             (BTC/ETH Futures,
    Equities, F&O)                 Crypto Options, Perps,
                                   Funding Rate)
        │
   NSE Scraper + yfinance
   (corporate actions, holidays,
    historical OHLCV fallback)
        │
   RBI / investing.com
   (economic event calendar)
```

### Frontend Stack
- React 18 + TypeScript + Vite
- TradingView Lightweight Charts (live charts with signal/S&R/Max Pain overlays)
- Recharts (analytics, P&L dashboards, payoff diagrams)
- Zustand (state management)
- WebSocket (real-time price + signal streaming)

### Backend Stack
- Python 3.11 + FastAPI (REST + WebSocket endpoints)
- Celery + Redis (background tasks, scheduled signal generation)
- SQLAlchemy + PostgreSQL + TimescaleDB (OHLCV hypertable, relational data)
- `pandas-ta` + `TA-Lib` (technical indicators)
- `py_vollib` / `mibian` (options Greeks — Indian F&O)
- `backtrader` (backtesting engine)
- `pyotp` + `bcrypt` (2FA + password hashing)
- `cryptography` (AES-256 API key vault)
- `APScheduler` (market-hours scheduling)

### Infrastructure
- Docker Compose (6 services: postgres-timescaledb, redis, backend, celery-worker, frontend, nginx)
- All image versions pinned; healthchecks on all services
- Nginx reverse proxy (single port entry for frontend + API)

---

## Implementation Phases — 62 Steps

### Phase 1: Foundation
1. Monorepo structure: `trading-bot/frontend/`, `trading-bot/backend/`, `trading-bot/docker/`
2. `docker-compose.yml` — 6 services with pinned image versions + healthchecks
3. `start.sh` / `start.bat` — checks Docker installed (prints install URL if missing); `docker compose pull && up -d --wait`
4. Database schema: `users`, `wallets`, `strategies`, `trades`, `positions`, `ohlcv` (TimescaleDB hypertable), `options_chain`, `signals`, `events`, `funding_rates`, `audit_log`
5. JWT authentication + `pyotp` 2FA; `bcrypt` password hashing; AES-256 encrypted broker API key vault; credentials never stored in plaintext
6. User roles: Admin, Trader — supports 5+ concurrent users with isolated data

### Phase 2: Market Data Engine *(depends on Phase 1)*
7. `BrokerAdapter` abstract class → `KiteAdapter` (Zerodha), `DeltaAdapter` (Delta Exchange) — pluggable for future brokers
8. Zerodha Kite WebSocket → TimescaleDB tick ingestion (Nifty50, BankNifty, top 50 equities OHLCV)
9. Historical OHLCV backfill on startup; `yfinance` fallback if Kite quota exceeded
10. NSE Options chain ingestion every 3 min during market hours (all strikes: OI, IV, bid/ask, last traded price)
11. India VIX real-time feed
12. NSE/BSE market hours enforcement + holiday calendar (no signals generated on exchange holidays)
13. **[GAP CLOSED] News & Economic Event Calendar** — scrape NSE corporate actions (earnings, dividends, splits), RBI MPC meeting schedule, NSE/BSE circulars; store in `events` table with impact level (high/medium/low); flag events on charts; used by Phase 4 event blackout filter
14. **[GAP CLOSED] Delta Exchange Funding Rate feed** — poll `/v2/funding_rate` + `/v2/funding_history` every 15 min; store in `funding_rates` timeseries; used by Phase 4 carry signal filter; displayed on crypto dashboard

### Phase 3: Technical Analysis Engine *(depends on Phase 2)*
15. Indicator library: EMA (9, 21, 50, 200), SMA, VWAP, RSI, MACD, Bollinger Bands, ATR, SuperTrend
16. Support/Resistance detector: swing high/low + volume cluster pivots (high-volume nodes from VPVR); primary source for SL placement
17. Price Action pattern engine: Doji, Hammer, Shooting Star, Bullish/Bearish Engulfing, Pin Bar, Inside Bar
18. Volume Profile / VPVR (volume at price — identifies high-volume nodes as S/R magnets)
19. Multi-timeframe confluence scorer (0–100): alignment across 1min / 5min / 15min / 1hr / Daily; entry gate = score ≥ 70
20. **[GAP CLOSED] Max Pain calculation engine** — per-expiry: iterate all strikes, compute sum of ITM call OI × (strike − spot) + ITM put OI × (spot − strike); max pain = strike minimising total pain for option buyers; recalculate every 3 min during market hours; output used as magnet target in expiry-week signal logic and chart overlay
21. **[GAP CLOSED] Dual Options Greeks engine** — *Indian F&O:* `py_vollib` Black-Scholes with current NSE risk-free rate; computes Delta, Theta, Gamma, Vega per strike; IV percentile vs. 52-week range. *Crypto:* Delta Exchange BTC/ETH IV surface; 25-delta risk reversal skew tracking; IV percentile for crypto

### Phase 4: Signal & Risk Engine *(depends on Phase 3)*
22. Signal generator: computes entry price, target (2:1 R:R minimum enforced), SL = `min(nearest S/R level, 1% of capital allocated to trade)`
23. Theta decay filter: suppress buy signals when ≤ 2 DTE on weekly contracts unless Gamma blast setup is detected
24. Gamma blast detector: unusual OI surge + IV spike on ATM strikes within 3 days of expiry → high-probability directional move signal
25. PCR contrarian signal: PCR < 0.7 = extreme bearish (potential reversal up); PCR > 1.3 = extreme bullish (potential reversal down)
26. **[GAP CLOSED] Kelly Criterion position sizing engine** — formula: `f* = (b·p − q) / b` where `b` = R:R ratio, `p` = strategy win rate (from backtest), `q` = 1 − p; apply half-Kelly (`f*/2`) for conservatism; VIX multiplier: ×1.0 at VIX < 15, ×0.5 at VIX 15–20, ×0 at VIX > 20 (no new trades); configurable per strategy between Kelly and fixed-fractional; hard caps: 5% portfolio per single trade, 20% per single instrument
27. **[GAP CLOSED] Event blackout filter** — before every signal generation, query `events` table; if high-impact event scheduled within ±30 min → block signal, log reason as "event blackout [event name]" in `audit_log`
28. **[GAP CLOSED] Funding rate carry filter (Delta Exchange)** — BTC/ETH perp funding rate > 0.1% per 8h → suppress long signals (longs paying heavy carry cost); funding rate < −0.05% per 8h → suppress short signals; funding rate displayed prominently on crypto dashboard
29. Daily circuit breaker: 3 SL hits in calendar day → halt all strategies for that user; manual reset required at start of next trading day
30. Weekly circuit breaker: rolling 5-trading-day portfolio drawdown ≥ 8% → halt all strategies for the week
31. Monthly circuit breaker: calendar-month portfolio drawdown ≥ 15% → halt all strategies; requires Admin override to resume
32. Strategy JSON config schema: `name`, `instruments[]`, `timeframes[]`, `indicators[]`, `entry_rules{}`, `exit_rules{}`, `automation_mode` (auto/semi), `wallet_type` (paper/real), `position_sizing_method` (kelly/fixed), `active` (bool)
33. **[NEW] Kill Switch engine** — three scopes processed with highest priority, bypassing all filters, circuit breakers, and approval windows:
    - **Global Kill:** cancel ALL open orders across ALL instruments and ALL strategies for the user; market-square-off ALL open positions via Kite `exit_order` + Delta `cancel_all_orders`; halt all Celery strategy workers; log event in `audit_log` with timestamp and initiator
    - **Per-instrument Kill:** cancel all open orders and square-off all positions for a single specified instrument (e.g., kill only BankNifty exposure while Nifty and crypto continue)
    - **Per-trade Kill:** cancel a specific open order or square-off a specific open position by trade ID
    - After Global Kill: all strategies automatically set to `active=false`; trader must manually re-enable each strategy before new trades resume
    - Exposed via: REST endpoint `POST /api/kill` (body: `{scope, instrument?, trade_id?}`); WebSocket command `kill:{scope}`; dashboard UI (Phase 8 step 56)

### Phase 5: Strategy Framework & Backtesting *(depends on Phase 4)*
33. Backtesting engine (backtrader): historical OHLCV replay using strategy JSON config; output metrics: win rate, expectancy, max drawdown, Sharpe ratio, profit factor, average trade duration
34. Walk-forward analysis: rolling in-sample / out-of-sample splits; Monte Carlo simulation (1000 randomised trade sequence runs) to validate strategy robustness and avoid overfitting
35. Paper trading engine: simulated order book with realistic slippage model (0.05% default, configurable per instrument); dummy wallet deduction on each paper fill; independent per user
36. Live strategy runner: dedicated Celery worker per active strategy; publishes signals to Redis pub/sub channel; consumed by execution engine (Phase 6) and UI (Phase 8)
37. **[GAP CLOSED] Multi-leg Options order builder** — leg templates: Bull Call Spread (buy lower-strike call + sell higher-strike call), Bear Put Spread, Iron Condor (sell ATM strangle + buy OTM protective wings), Straddle (buy ATM call + ATM put), Strangle (buy OTM call + OTM put); system computes: net premium paid/received, max profit, max loss, upper/lower breakeven points; signals carry all leg details; execution in Phase 6 sends all legs atomically
38. Strategy activate/deactivate toggle per user; each user maintains independent sets of active strategies; Admin can view all users' strategy states

### Phase 6: Execution & Wallets *(depends on Phase 5)*
39. Real order execution: market, limit, SL-M order types via `KiteAdapter` (NSE) and `DeltaAdapter` (crypto)
40. Per-strategy automation mode: **Auto** → execute immediately on signal; **Semi** → push signal via WebSocket to user dashboard → 30-second approval window → auto-cancel and log "expired" if no user action
41. Multi-leg atomic execution: send all legs in parallel; if any leg fill fails → immediately cancel/reverse remaining legs; log partial-fill alert in `audit_log` and notify user
42. **[NEW] Kill Switch execution handler** — dedicated high-priority Celery queue (`kill_queue`) separate from normal order queue; processes kill commands ahead of all pending tasks:
    - Global Kill: iterate all open positions → send market exit order for each → cancel all pending open orders → publish `kill:global` event to Redis → all strategy workers receive signal and stop
    - Per-instrument Kill: filter positions/orders by instrument → same exit flow
    - Per-trade Kill: look up trade by ID → cancel or market-exit that single trade
    - Kill confirmation: WebSocket push to user dashboard showing count of positions closed and orders cancelled; logged to `audit_log`
    - Telegram notification sent immediately: "🔴 KILL SWITCH ACTIVATED — [scope] — [N] positions closed, [M] orders cancelled at [timestamp]"
43. Real wallet: read Kite/Delta account balance and available margin (read-only mirror); order placement permission scoped per strategy
44. Dummy (paper) wallet: configurable virtual capital per user (e.g., ₹10,00,000 default); deduct/credit on simulated fills; resets to initial capital on demand; separate from real wallet
45. Slippage fill tracker: for every real order, log expected price (signal price at time of generation) vs. actual fill price; compute average slippage per instrument over rolling 30 days; displayed in admin panel

### Phase 7: Portfolio & Risk *(parallel with Phase 6)*
45. Kelly Criterion output (Phase 4 step 26) translated to exact lot count per instrument; all position caps enforced before order submission
46. Real-time portfolio P&L tracker: unrealized + realized P&L across all open positions; updates on every tick
47. Margin utilisation monitor: alert in-app at 70% margin used; block new order submissions at 90% margin used; display in dashboard header
48. **[GAP CLOSED] Correlation matrix** — Nifty / BankNifty / BTC / top equities: Pearson correlation recomputed daily using 30-day rolling returns; displayed as heatmap on portfolio dashboard; warn user if 2 or more positions with correlation > 0.8 are open simultaneously (concentration risk)

### Phase 8: Dashboards & UI *(depends on Phase 6, 7)*
49. **Watchlist dashboard** — user-personalised instrument lists (NSE equities + F&O + crypto); live price tiles with % change, mini sparklines; event calendar sidebar showing upcoming RBI dates, earnings, expiry dates
50. **Live chart** — TradingView Lightweight Charts; overlaid: buy/sell signal arrows, S/R horizontal lines, SL band (red), target band (green), Max Pain strike vertical line (options charts), event date markers, VIX indicator panel
51. **Strategy dashboard** — per-strategy: P&L curve, win rate, expectancy, open positions, full trade history, activate/deactivate toggle; circuit breaker status badge (active/daily-halted/weekly-halted/monthly-halted)
52. **Options chain dashboard** — full NSE options chain table per expiry: OI, OI change, IV, Delta, Theta, Gamma, bid/ask; PCR displayed; Max Pain strike highlighted; separate crypto options chain with funding rate prominently shown
53. **Multi-leg strategy builder UI** — visual drag-and-drop leg constructor; select strategy template or build custom; real-time payoff diagram (profit/loss curve vs. underlying price at expiry); breakeven points, max profit, max loss displayed
54. **Trade journal** — full chronological audit log: every signal generated, event blackout suppressions (with event name), semi-auto approval/rejection, order submission, fill confirmation, SL hit, target hit, circuit breaker events
55. **Admin panel** — user management (create/edit/suspend users); system health dashboard: data feed status per instrument, Kite WebSocket connection status, Delta Exchange connection status, Celery worker status, funding rate last-updated timestamp; average slippage table
56. **[NEW] Kill Switch UI** — prominent red "KILL" button pinned in dashboard header (always visible on every page, never hidden in menus); click opens scope modal: Global / By Instrument (dropdown) / By Trade ID (input); Global Kill requires a second "Yes, kill all" confirmation to prevent accidental activation; keyboard shortcut `Ctrl+Shift+K` triggers Global Kill scope modal; per-trade Kill button available inline on every open position row; after kill executes, dashboard displays real-time count of positions closed and orders cancelled

### Phase 9: Notifications *(parallel with Phase 8)*
56. In-app WebSocket real-time alerts (toast notifications): trade signal generated, SL hit, target reached, circuit breaker triggered (daily/weekly/monthly), event blackout active, margin warning (70%), margin block (90%)
57. Telegram bot notifications per user (configurable on/off per alert type): recommended for trading alerts in India — most reliable delivery; bot sends formatted signal cards with entry/SL/target/R:R
58. Daily summary: P&L summary sent at 3:45 PM IST (15 min after NSE market close); crypto 24h summary sent at midnight IST; both via Telegram + in-app

### Phase 10: Portability & Launch *(depends on all above)*
59. `start.sh` (Linux/macOS) + `start.bat` (Windows): check Docker installed → if missing, print official install URL and exit with clear message; check `docker compose` v2 available; run `docker compose pull && docker compose up -d --wait`; print application URL on success
60. First-run wizard (runs if `.env` absent): interactive prompts for Kite API key + secret, Delta Exchange API key + secret, admin username/password; encrypt credentials using AES-256 → write to `.env` (gitignored); commit `.env.example` with placeholder values
61. `docker-compose.yml`: pinned image versions — `timescale/timescaledb:latest-pg16`, `redis:7.2-alpine`, `python:3.11-slim`, `node:20-alpine`, `nginx:1.25-alpine`; healthchecks on all 6 services; `depends_on` with condition `service_healthy`
62. `README.md`: one-command launch guide; prerequisites (Docker Desktop); first-run wizard instructions; broker API key setup links; SEBI algo registration note

---

## Key Files to Create

| File | Purpose |
|---|---|
| `trading-bot/docker-compose.yml` | Full stack orchestration (pinned versions, healthchecks) |
| `trading-bot/start.sh` + `start.bat` | Portable launcher with dep checks |
| `trading-bot/backend/requirements.txt` | Python: fastapi, uvicorn, kiteconnect, delta-rest-client, pandas-ta, TA-Lib, py_vollib, backtrader, celery, redis, sqlalchemy, alembic, psycopg2, pyotp, cryptography, APScheduler, httpx |
| `trading-bot/frontend/package.json` | Node: react, typescript, vite, zustand, lightweight-charts, recharts, @tanstack/react-query |
| `trading-bot/backend/app/brokers/kite_adapter.py` | Zerodha Kite Connect integration (WebSocket + REST orders) |
| `trading-bot/backend/app/brokers/delta_adapter.py` | Delta Exchange integration (WebSocket + REST orders + funding rate) |
| `trading-bot/backend/app/engines/signal_engine.py` | Signal generation, 2:1 R:R enforcement, SL calc, event blackout filter, funding rate filter |
| `trading-bot/backend/app/engines/max_pain.py` | Max Pain calculation from live options chain OI |
| `trading-bot/backend/app/engines/greeks_engine.py` | Indian F&O Greeks (py_vollib) + Delta Exchange crypto Greeks + IV skew |
| `trading-bot/backend/app/engines/backtesting_engine.py` | backtrader wrapper + walk-forward + Monte Carlo (1000 runs) |
| `trading-bot/backend/app/engines/paper_trading.py` | Simulated order book, slippage model, dummy wallet |
| `trading-bot/backend/app/engines/multi_leg_builder.py` | Options strategy leg templates + payoff/breakeven computation |
| `trading-bot/backend/app/engines/kelly_sizer.py` | Kelly Criterion formula + half-Kelly + VIX multiplier |
| `trading-bot/backend/app/core/risk_manager.py` | Daily/weekly/monthly circuit breaker, margin monitor, correlation check |
| `trading-bot/backend/app/data/event_calendar.py` | NSE/RBI event ingestion, impact classification, blackout logic |
| `trading-bot/backend/app/data/funding_rate.py` | Delta Exchange funding rate poller + carry filter |
| `trading-bot/backend/app/core/kill_switch.py` | Kill Switch engine — global/per-instrument/per-trade scope; high-priority Celery queue handler |
| `trading-bot/frontend/src/components/charts/` | TradingView chart + signal/S&R/Max Pain/event overlays |
| `trading-bot/frontend/src/components/dashboards/` | Strategy, options chain, watchlist, multi-leg builder UIs |
| `trading-bot/frontend/src/components/KillSwitch.tsx` | Always-visible kill button with scope modal + confirmation UX |

---

## Verification Plan

| Test | Expected Result |
|---|---|
| Signal engine: 2:1 R:R enforcement | No signal emitted with R:R < 2.0 |
| Signal engine: SL ≤ 1% capital | SL never exceeds 1% of allocated capital regardless of S/R position |
| Event blackout: inject high-impact event | Signal blocked; `audit_log` entry reads "event blackout [RBI MPC]" |
| Kelly sizer: VIX = 25 | Position size = 0 lots (VIX multiplier = 0) |
| Kelly sizer: known p and b | Output matches `f* = (b·p − q) / b` formula |
| Max Pain: known OI table | Output matches manually calculated max pain strike |
| Funding rate filter: rate > 0.1%/8h | Long signals suppressed; short signals pass through |
| Daily circuit breaker | After 3rd SL hit, all strategy workers stop; 4th signal not generated |
| Weekly circuit breaker | At 8% rolling drawdown, strategies halt; confirmed in UI badge |
| Monthly circuit breaker | At 15% monthly drawdown, halt; only Admin override resumes |
| Backtest (Nifty 2023 data) | Win rate / drawdown matches manual calculation ±2% |
| Multi-leg payoff: Iron Condor | Max profit = net premium received; max loss = wing width − net premium |
| Paper trade 1 week | Dummy wallet balance matches expected fills with 0.05% slippage applied |
| Multi-user isolation | 5 simultaneous sessions; each user sees only their own strategies and trades |
| Portability | Fresh machine with only Docker Desktop → `start.sh` → full stack running |
| Semi-auto approval | Signal pushed; user approves within 30s → order placed; no action → auto-cancelled |
| Kill Switch — Global | Click Global Kill → all open orders cancelled, all positions market-squared-off, all strategy workers halted within 1 tick |
| Kill Switch — Per-instrument | Kill BankNifty only → only BankNifty orders cancelled and positions closed; Nifty and crypto unaffected |
| Kill Switch — Per-trade | Kill trade ID #123 → that single position closed; all others continue |
| Kill Switch — accidental prevention | Second confirmation required for Global Kill; keyboard shortcut requires confirmation modal |

---

## Out of Scope (v1)

- **Tax Audit Trail** (STCG/LTCG/F&O export) — excluded per user decision
- **ML/AI price prediction models** — planned for v2 (see explanation below)
- **Mobile app** — PWA from browser sufficient for v1
- **Multi-broker simultaneous execution** — single broker per environment for v1
- **Direct NSE/BSE co-location connectivity**

### Why ML Price Prediction is v2, Not v1

ML price prediction means training statistical or deep-learning models (LSTM, Transformer, XGBoost, Reinforcement Learning) on historical market data to forecast future price direction or magnitude.

**Reason 1 — Data dependency.** ML models need 2–5 years of clean, normalised, tick-level data to train meaningfully on Indian markets. The data pipeline (Phase 2) must run for several months before there is enough high-quality in-house data. Training on raw yfinance OHLCV data alone produces unreliable models due to survivorship bias and data quality issues.

**Reason 2 — Non-stationarity risk.** Financial time series change statistical properties between market regimes (bull, bear, sideways, high-VIX, low-VIX). A model trained on 2021 Nifty data will fail badly in a 2022 bear market. Without the Phase 5 walk-forward backtesting infrastructure already in production, there is no safe way to detect when an ML model has drifted and needs retraining.

**Reason 3 — Build order.** ML works best as a *confidence layer on top of* rule-based signals, not as a replacement. The v1 signal engine (Price Action + Volume Profile + Multi-timeframe confluence + Greeks + PCR + Kelly sizing) is a complete, battle-tested, rules-based system used by professional traders. ML in v2 will rank and filter those signals — not replace them.

**Reason 4 — Regulatory clarity.** SEBI's algorithmic trading framework is clearer for rule-based strategies (the logic is auditable and explainable). ML "black box" decisions add compliance complexity. Rule-based v1 strategies are easier to register with Zerodha as approved algos.

**What ML adds in v2 (after 6–12 months of live data collection):**
- **Regime classifier** (XGBoost) — detects trending vs. ranging vs. high-volatility market regime; automatically switches which strategy set is active
- **Signal confidence scorer** (LSTM/Transformer) — assigns a 0–100 probability score to each rule-based signal; only executes signals scoring above a threshold
- **Reinforcement Learning agent** — learns optimal entry timing within a signal window (e.g., waits for a pullback to enter rather than entering immediately)
- **Anomaly detector** — flags unusual price/volume behaviour not covered by rules (flash crashes, block deals, circuit filters)
- **News sentiment classifier** — NLP on NSE announcements, RBI press releases, and financial news headlines to quantify sentiment impact on signal direction

---

## Important Regulatory Note

Algorithmic trading in India requires broker-side algo approval under SEBI regulations. Zerodha requires each strategy to be registered as an algo via their compliance team before live automated execution. This is a mandatory regulatory step the user must complete before enabling "Auto" mode on real trades. Paper trading and semi-automatic mode (user approves each trade) do not require algo registration.
