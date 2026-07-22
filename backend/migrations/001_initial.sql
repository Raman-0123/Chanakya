-- CHANAKYA system-of-record schema. Safe to apply repeatedly.
CREATE TABLE IF NOT EXISTS domain_events (
  id TEXT PRIMARY KEY,
  deduplication_key TEXT UNIQUE NOT NULL,
  category TEXT NOT NULL,
  source TEXT NOT NULL,
  provenance TEXT NOT NULL,
  observed_at TIMESTAMPTZ NOT NULL,
  ingested_at TIMESTAMPTZ NOT NULL,
  risk_score DOUBLE PRECISION NOT NULL,
  payload JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_domain_events_observed ON domain_events(observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_domain_events_category ON domain_events(category);
CREATE INDEX IF NOT EXISTS idx_domain_events_risk ON domain_events(risk_score DESC);

CREATE TABLE IF NOT EXISTS source_observations (
  id BIGSERIAL PRIMARY KEY,
  event_id TEXT NOT NULL,
  source TEXT NOT NULL,
  observed_at TIMESTAMPTZ NOT NULL,
  raw_hash TEXT NOT NULL,
  source_url TEXT,
  payload JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS workflow_runs (
  id TEXT PRIMARY KEY,
  scenario_id TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  payload JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS strategies (
  id TEXT PRIMARY KEY,
  workflow_run_id TEXT NOT NULL,
  strategy_id TEXT NOT NULL,
  rank INTEGER NOT NULL,
  payload JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS missions (
  id TEXT PRIMARY KEY,
  workflow_run_id TEXT,
  scenario_id TEXT NOT NULL,
  strategy_id TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  activated_at TIMESTAMPTZ,
  payload JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS execution_audit (
  id BIGSERIAL PRIMARY KEY,
  mission_id TEXT NOT NULL,
  action TEXT NOT NULL,
  occurred_at TIMESTAMPTZ NOT NULL,
  payload JSONB NOT NULL
);
