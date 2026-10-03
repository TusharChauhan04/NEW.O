-- ============================================================
--  NeuralOrbit — Integration Module Schema (L1)
--  Run this in Supabase SQL Editor AFTER init_db.sql
-- ============================================================

-- ── integrations ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS integrations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    module          TEXT NOT NULL,    -- 'crm' | 'marketing' | 'website' | 'shield'
    platform        TEXT NOT NULL,    -- 'zoho' | 'hubspot' | 'custom' | 'webhook' | 'meta_ads' | ...
    type            TEXT DEFAULT 'webhook',  -- 'webhook' | 'api_key' | 'oauth'
    label           TEXT,
    status          TEXT DEFAULT 'active',   -- 'active' | 'error' | 'disconnected'
    config          JSONB DEFAULT '{}',      -- platform-specific config
    webhook_secret  TEXT,                    -- HMAC signing secret
    last_sync_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, module, platform, label)
);

-- ── integration_api_keys ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS integration_api_keys (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    integration_id  UUID REFERENCES integrations(id) ON DELETE CASCADE,
    key_prefix      TEXT NOT NULL,           -- First 8 chars for display (no_live_...)
    key_hash        TEXT NOT NULL UNIQUE,    -- SHA-256 hash of full key
    label           TEXT,
    last_used_at    TIMESTAMPTZ,
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── raw_integration_events ────────────────────────────────────
-- Raw inbound payloads before normalization into events table
CREATE TABLE IF NOT EXISTS raw_integration_events (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    integration_id  UUID REFERENCES integrations(id) ON DELETE CASCADE,
    user_id         UUID REFERENCES auth.users(id),
    platform        TEXT NOT NULL,
    raw_payload     JSONB NOT NULL,
    normalized      BOOLEAN DEFAULT false,
    error           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Indexes ───────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_integrations_user      ON integrations(user_id);
CREATE INDEX IF NOT EXISTS idx_integrations_module    ON integrations(user_id, module);
CREATE INDEX IF NOT EXISTS idx_api_keys_hash          ON integration_api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_raw_events_integration ON raw_integration_events(integration_id);
CREATE INDEX IF NOT EXISTS idx_raw_events_normalized  ON raw_integration_events(normalized);

-- ── Row Level Security ────────────────────────────────────────
ALTER TABLE integrations             ENABLE ROW LEVEL SECURITY;
ALTER TABLE integration_api_keys     ENABLE ROW LEVEL SECURITY;
ALTER TABLE raw_integration_events   ENABLE ROW LEVEL SECURITY;

CREATE POLICY "own_integrations"      ON integrations           FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "own_api_keys"          ON integration_api_keys   FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "own_raw_events"        ON raw_integration_events FOR ALL USING (auth.uid() = user_id);
