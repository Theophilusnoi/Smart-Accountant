-- PostgreSQL 15+. Money in NUMERIC(14,2); all timestamps timestamptz (UTC).
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;

CREATE TYPE sub_status     AS ENUM ('trialing','active','past_due','canceled','expired');
CREATE TYPE account_status AS ENUM ('active','paused','passed','failed','archived');
CREATE TYPE trade_side     AS ENUM ('long','short');
CREATE TYPE trade_status   AS ENUM ('pending','open','closed','rejected','canceled');

CREATE TABLE users (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email           citext UNIQUE NOT NULL,        
  password_hash   text,                            -- null if SSO/Whop-only login
  tz              text NOT NULL DEFAULT 'America/New_York',
  risk_ack_at     timestamptz,                     -- accepted risk disclosure; required before bot can run
  tos_ack_version text,
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE subscriptions (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  provider        text NOT NULL DEFAULT 'whop',
  provider_sub_id text UNIQUE NOT NULL,
  plan            text NOT NULL CHECK (plan IN ('monthly','quarterly','annual')),
  status          sub_status NOT NULL,
  max_accounts    int NOT NULL DEFAULT 1,
  current_period_end timestamptz NOT NULL,
  updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON subscriptions (user_id, status);

-- Versioned firm rule sets; accounts pin a version so rule changes are explicit.
CREATE TABLE firm_rule_sets (
  id                    serial PRIMARY KEY,
  firm                  text NOT NULL,             -- 'lucidflex'
  account_size          numeric(14,2) NOT NULL,
  version               int NOT NULL,
  profit_target         numeric(14,2) NOT NULL,
  max_loss              numeric(14,2) NOT NULL,
  drawdown_lock_balance numeric(14,2),
  consistency_ratio     numeric(4,3),
  firm_daily_loss_limit numeric(14,2),
  flatten_by_et         time NOT NULL,
  verified_at           date NOT NULL,             -- when someone last checked the firm's site
  source_url            text,
  UNIQUE (firm, account_size, version)
);

CREATE TABLE trading_accounts (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id            uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  label              text NOT NULL,
  firm_rule_set_id   int  NOT NULL REFERENCES firm_rule_sets(id),
  bridge             text NOT NULL DEFAULT 'tradeus',
  bridge_account_ref text NOT NULL,                -- bridge's id for the account, never firm login
  bridge_secret_ref  text NOT NULL,                -- pointer into KMS/Vault; secret itself never stored here
  instrument         text NOT NULL DEFAULT 'MNQ',
  status             account_status NOT NULL DEFAULT 'paused',
  bot_enabled        boolean NOT NULL DEFAULT false,
  risk_config        jsonb NOT NULL DEFAULT '{}',  -- overrides of BotRiskConfig
  risk_state         jsonb NOT NULL,               -- serialized AccountState (balance, floor, counters)
  risk_state_version bigint NOT NULL DEFAULT 0,    -- optimistic locking for engine writes
  created_at         timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, bridge, bridge_account_ref)
);

CREATE TABLE bot_sessions (
  id             bigserial PRIMARY KEY,
  account_id     uuid NOT NULL REFERENCES trading_accounts(id) ON DELETE CASCADE,
  trading_day    date NOT NULL,
  session_name   text NOT NULL,
  started_at     timestamptz NOT NULL,
  ended_at       timestamptz,
  trades         int NOT NULL DEFAULT 0,
  losses         int NOT NULL DEFAULT 0,
  end_reason     text,                             -- HaltReason value
  UNIQUE (account_id, trading_day, session_name)
);

CREATE TABLE signals (
  id            bigserial PRIMARY KEY,
  account_id    uuid NOT NULL REFERENCES trading_accounts(id) ON DELETE CASCADE,
  bot_session_id bigint REFERENCES bot_sessions(id),
  generated_at  timestamptz NOT NULL,
  instrument    text NOT NULL,
  side          trade_side NOT NULL,
  entry         numeric(14,4) NOT NULL,
  stop          numeric(14,4) NOT NULL,
  target        numeric(14,4) NOT NULL,
  strategy_ver  text NOT NULL,
  features      jsonb                              -- inputs that produced the signal, for replay
);

CREATE TABLE trades (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id      uuid NOT NULL REFERENCES trading_accounts(id) ON DELETE CASCADE,
  signal_id       bigint REFERENCES signals(id),
  client_order_id text UNIQUE NOT NULL,            -- idempotency key sent to the bridge
  side            trade_side NOT NULL,
  contracts       int NOT NULL CHECK (contracts > 0),
  entry_price     numeric(14,4),
  stop_price      numeric(14,4) NOT NULL,
  target_price    numeric(14,4) NOT NULL,
  exit_price      numeric(14,4),
  risk_usd        numeric(14,2) NOT NULL,
  pnl_usd         numeric(14,2),
  fees_usd        numeric(14,2) NOT NULL DEFAULT 0,
  status          trade_status NOT NULL DEFAULT 'pending',
  exit_reason     text,                            -- 'stop','target','flatten','manual','risk_halt'
  opened_at       timestamptz,
  closed_at       timestamptz
);
CREATE INDEX ON trades (account_id, opened_at DESC);

-- Append-only audit log: every signal, risk decision, order, fill, and halt.
CREATE TABLE audit_events (
  id          bigserial PRIMARY KEY,
  account_id  uuid REFERENCES trading_accounts(id) ON DELETE SET NULL,
  at          timestamptz NOT NULL DEFAULT now(),
  kind        text NOT NULL,                       -- 'risk_decision','order_sent','fill','halt',...
  payload     jsonb NOT NULL
);
CREATE INDEX ON audit_events (account_id, at DESC);
CREATE INDEX ON audit_events (kind, at DESC);

-- Daily rollup for dashboard + consistency display.
CREATE TABLE daily_results (
  account_id   uuid NOT NULL REFERENCES trading_accounts(id) ON DELETE CASCADE,
  trading_day  date NOT NULL,
  start_balance numeric(14,2) NOT NULL,
  end_balance  numeric(14,2) NOT NULL,
  floor_after  numeric(14,2) NOT NULL,
  pnl          numeric(14,2) GENERATED ALWAYS AS (end_balance - start_balance) STORED,
  PRIMARY KEY (account_id, trading_day)
);
