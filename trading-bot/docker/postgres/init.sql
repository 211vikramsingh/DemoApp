-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- ── Users ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    username    VARCHAR(50) UNIQUE NOT NULL,
    email       VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    totp_secret_enc TEXT,            -- AES-256 encrypted TOTP secret
    role        VARCHAR(20) NOT NULL DEFAULT 'trader',  -- 'admin' | 'trader'
    is_active   BOOLEAN     NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Wallets ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS wallets (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    wallet_type     VARCHAR(10) NOT NULL,   -- 'real' | 'paper'
    currency        VARCHAR(10) NOT NULL DEFAULT 'INR',
    balance         NUMERIC(20,4) NOT NULL DEFAULT 0,
    initial_balance NUMERIC(20,4) NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Strategies ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS strategies (
    id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name                    VARCHAR(100) NOT NULL,
    config                  JSONB       NOT NULL DEFAULT '{}',
    automation_mode         VARCHAR(10) NOT NULL DEFAULT 'semi',  -- 'auto' | 'semi'
    wallet_type             VARCHAR(10) NOT NULL DEFAULT 'paper', -- 'paper' | 'real'
    position_sizing_method  VARCHAR(20) NOT NULL DEFAULT 'kelly', -- 'kelly' | 'fixed'
    is_active               BOOLEAN     NOT NULL DEFAULT false,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Signals ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS signals (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id     UUID        NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    user_id         UUID        NOT NULL REFERENCES users(id),
    instrument      VARCHAR(50) NOT NULL,
    direction       VARCHAR(10) NOT NULL,   -- 'long' | 'short'
    entry           NUMERIC(20,4) NOT NULL,
    stop_loss       NUMERIC(20,4) NOT NULL,
    target          NUMERIC(20,4) NOT NULL,
    rr_ratio        NUMERIC(6,2)  NOT NULL,
    confidence_score INT,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- pending | executed | rejected | expired | blocked
    block_reason    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Trades ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS trades (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID        NOT NULL REFERENCES users(id),
    strategy_id     UUID        REFERENCES strategies(id),
    signal_id       UUID        REFERENCES signals(id),
    instrument      VARCHAR(50) NOT NULL,
    direction       VARCHAR(10) NOT NULL,
    entry_price     NUMERIC(20,4) NOT NULL,
    exit_price      NUMERIC(20,4),
    stop_loss       NUMERIC(20,4) NOT NULL,
    target          NUMERIC(20,4) NOT NULL,
    quantity        INT         NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'open',
    -- open | closed | cancelled | killed
    wallet_type     VARCHAR(10) NOT NULL,
    broker_order_id VARCHAR(100),
    pnl             NUMERIC(20,4),
    slippage        NUMERIC(20,4),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at       TIMESTAMPTZ
);

-- ── OHLCV (TimescaleDB hypertable) ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ohlcv (
    time        TIMESTAMPTZ NOT NULL,
    instrument  VARCHAR(50) NOT NULL,
    timeframe   VARCHAR(10) NOT NULL,  -- '1min','5min','15min','1hr','1day'
    open        NUMERIC(20,4) NOT NULL,
    high        NUMERIC(20,4) NOT NULL,
    low         NUMERIC(20,4) NOT NULL,
    close       NUMERIC(20,4) NOT NULL,
    volume      BIGINT       NOT NULL
);

SELECT create_hypertable('ohlcv', 'time', if_not_exists => TRUE);
CREATE UNIQUE INDEX IF NOT EXISTS ohlcv_instrument_timeframe_time
    ON ohlcv (instrument, timeframe, time DESC);

-- ── Options Chain ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS options_chain (
    time            TIMESTAMPTZ NOT NULL,
    underlying      VARCHAR(50) NOT NULL,
    expiry          DATE        NOT NULL,
    strike          NUMERIC(10,2) NOT NULL,
    option_type     VARCHAR(5) NOT NULL,  -- 'CE' | 'PE'
    oi              BIGINT,
    oi_change       BIGINT,
    iv              NUMERIC(8,4),
    ltp             NUMERIC(10,4),
    bid             NUMERIC(10,4),
    ask             NUMERIC(10,4),
    delta           NUMERIC(8,4),
    theta           NUMERIC(8,4),
    gamma           NUMERIC(8,4),
    vega            NUMERIC(8,4)
);

SELECT create_hypertable('options_chain', 'time', if_not_exists => TRUE);

-- ── Events (Economic Calendar) ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS events (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    title           VARCHAR(255) NOT NULL,
    event_type      VARCHAR(50)  NOT NULL,
    -- 'rbi_mpc' | 'earnings' | 'dividend' | 'expiry' | 'economic'
    impact          VARCHAR(10)  NOT NULL DEFAULT 'medium',
    -- 'high' | 'medium' | 'low'
    instrument      VARCHAR(50),  -- NULL = market-wide
    scheduled_at    TIMESTAMPTZ  NOT NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS events_scheduled_at ON events (scheduled_at);

-- ── Funding Rates (Delta Exchange) ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS funding_rates (
    time        TIMESTAMPTZ NOT NULL,
    instrument  VARCHAR(50) NOT NULL,
    rate        NUMERIC(10,6) NOT NULL
);

SELECT create_hypertable('funding_rates', 'time', if_not_exists => TRUE);

-- ── Audit Log ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        REFERENCES users(id),
    event_type  VARCHAR(50) NOT NULL,
    description TEXT        NOT NULL,
    metadata    JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS audit_log_user_id_created ON audit_log (user_id, created_at DESC);
