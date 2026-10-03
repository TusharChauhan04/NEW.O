-- =============================================================================
--  DEPRECATED — DO NOT RUN
--
--  Superseded by: migrations/000_baseline_schema.sql
--
--  This was one of three overlapping "full schema" scripts that had drifted
--  apart from each other (notably the UNIQUE constraint on `integrations`).
--  Kept only for historical reference. Running it may reintroduce that drift.
--  See migrations/README.md for the correct setup order.
-- =============================================================================

-- ============================================================
--  NeuralOrbit — Safe Re-Run Script (idempotent)
--  Run this if you already ran init_db.sql and got policy errors.
--  This drops and recreates all RLS policies safely.
-- ============================================================

-- ── Extensions (idempotent) ───────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ── Tables (idempotent — IF NOT EXISTS) ───────────────────
CREATE TABLE IF NOT EXISTS events (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    module      TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    payload     JSONB DEFAULT '{}',
    context     JSONB DEFAULT '{}',
    source      TEXT DEFAULT 'api',
    sandbox     BOOLEAN DEFAULT false,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS decisions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    module          TEXT NOT NULL,
    action          TEXT NOT NULL,
    reasoning       TEXT,
    confidence      FLOAT,
    state_snapshot  JSONB DEFAULT '{}',
    alternatives    JSONB DEFAULT '[]',
    outcome         TEXT DEFAULT 'pending',
    override_enabled BOOLEAN DEFAULT false,
    override_by     TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rewards (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id      UUID REFERENCES events(id) ON DELETE SET NULL,
    decision_id   UUID REFERENCES decisions(id) ON DELETE SET NULL,
    user_id       UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    module        TEXT NOT NULL,
    event_type    TEXT NOT NULL,
    reward_value  FLOAT NOT NULL,
    reward_source TEXT DEFAULT 'rule_engine',
    notes         TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS reward_config (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    module        TEXT NOT NULL,
    event_type    TEXT NOT NULL,
    reward_value  FLOAT NOT NULL,
    description   TEXT,
    is_active     BOOLEAN DEFAULT true,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (module, event_type)
);

CREATE TABLE IF NOT EXISTS module_states (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id           UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    module            TEXT NOT NULL,
    state             JSONB DEFAULT '{}',
    cumulative_reward FLOAT DEFAULT 0,
    decision_count    INT DEFAULT 0,
    last_updated      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, module)
);

CREATE TABLE IF NOT EXISTS memory_vectors (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    module      TEXT NOT NULL,
    content     TEXT NOT NULL,
    embedding   vector(1536),
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bandit_arms (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    module      TEXT NOT NULL,
    arm_key     TEXT NOT NULL,
    alpha       FLOAT DEFAULT 1.0,
    beta        FLOAT DEFAULT 1.0,
    total_pulls INT DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, module, arm_key)
);

-- Integration tables
CREATE TABLE IF NOT EXISTS integrations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    module          TEXT NOT NULL,
    platform        TEXT NOT NULL,
    type            TEXT DEFAULT 'webhook',
    label           TEXT,
    status          TEXT DEFAULT 'active',
    config          JSONB DEFAULT '{}',
    webhook_secret  TEXT,
    last_sync_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, module, platform, label)
);

CREATE TABLE IF NOT EXISTS integration_api_keys (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    integration_id  UUID REFERENCES integrations(id) ON DELETE CASCADE,
    key_prefix      TEXT NOT NULL,
    key_hash        TEXT NOT NULL UNIQUE,
    label           TEXT,
    last_used_at    TIMESTAMPTZ,
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

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

CREATE TABLE IF NOT EXISTS user_reward_config (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    conversion  INT NOT NULL DEFAULT 75,
    retention   INT NOT NULL DEFAULT 85,
    cost        INT NOT NULL DEFAULT 40,
    risk        INT NOT NULL DEFAULT 30,
    industry    TEXT NOT NULL DEFAULT 'SaaS',
    sim_mode    BOOLEAN NOT NULL DEFAULT true,
    updated_by  TEXT,
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id)
);

CREATE TABLE IF NOT EXISTS user_autonomy_config (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id        UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    global_level   TEXT NOT NULL DEFAULT 'assist' CHECK (global_level IN ('observe','assist','autonomous')),
    crm            TEXT NOT NULL DEFAULT 'assist' CHECK (crm IN ('observe','assist','autonomous')),
    marketing      TEXT NOT NULL DEFAULT 'assist' CHECK (marketing IN ('observe','assist','autonomous')),
    shield         TEXT NOT NULL DEFAULT 'observe' CHECK (shield IN ('observe','assist','autonomous')),
    website        TEXT NOT NULL DEFAULT 'autonomous' CHECK (website IN ('observe','assist','autonomous')),
    locked_modules JSONB NOT NULL DEFAULT '[]',
    updated_by     TEXT,
    updated_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id)
);

-- ── Indexes ───────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_events_user_module    ON events(user_id, module);
CREATE INDEX IF NOT EXISTS idx_events_created_at     ON events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_decisions_user_module  ON decisions(user_id, module);
CREATE INDEX IF NOT EXISTS idx_rewards_user_module   ON rewards(user_id, module);
CREATE INDEX IF NOT EXISTS idx_rewards_created_at    ON rewards(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memory_user_module    ON memory_vectors(user_id, module);
CREATE INDEX IF NOT EXISTS idx_memory_embedding      ON memory_vectors USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_integrations_user     ON integrations(user_id);
CREATE INDEX IF NOT EXISTS idx_integrations_module   ON integrations(user_id, module);
CREATE INDEX IF NOT EXISTS idx_api_keys_hash         ON integration_api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_raw_events_integration ON raw_integration_events(integration_id);

-- ── Row Level Security ─────────────────────────────────────
ALTER TABLE events              ENABLE ROW LEVEL SECURITY;
ALTER TABLE decisions           ENABLE ROW LEVEL SECURITY;
ALTER TABLE rewards             ENABLE ROW LEVEL SECURITY;
ALTER TABLE module_states       ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_vectors      ENABLE ROW LEVEL SECURITY;
ALTER TABLE bandit_arms         ENABLE ROW LEVEL SECURITY;
ALTER TABLE reward_config       ENABLE ROW LEVEL SECURITY;
ALTER TABLE integrations        ENABLE ROW LEVEL SECURITY;
ALTER TABLE integration_api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE raw_integration_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_reward_config  ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_autonomy_config ENABLE ROW LEVEL SECURITY;

-- ── DROP + RECREATE Policies (idempotent) ─────────────────
DROP POLICY IF EXISTS "own_events"      ON events;
DROP POLICY IF EXISTS "own_decisions"   ON decisions;
DROP POLICY IF EXISTS "own_rewards"     ON rewards;
DROP POLICY IF EXISTS "own_states"      ON module_states;
DROP POLICY IF EXISTS "own_memory"      ON memory_vectors;
DROP POLICY IF EXISTS "own_bandits"     ON bandit_arms;
DROP POLICY IF EXISTS "read_reward_config" ON reward_config;
DROP POLICY IF EXISTS "own_integrations"   ON integrations;
DROP POLICY IF EXISTS "own_api_keys"       ON integration_api_keys;
DROP POLICY IF EXISTS "own_raw_events"     ON raw_integration_events;
DROP POLICY IF EXISTS "own_reward_config"  ON user_reward_config;
DROP POLICY IF EXISTS "own_autonomy_config" ON user_autonomy_config;

CREATE POLICY "own_events"      ON events             FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "own_decisions"   ON decisions          FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "own_rewards"     ON rewards            FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "own_states"      ON module_states      FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "own_memory"      ON memory_vectors     FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "own_bandits"     ON bandit_arms        FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "own_integrations" ON integrations      FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "own_api_keys"    ON integration_api_keys FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "own_raw_events"  ON raw_integration_events FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "own_reward_config" ON user_reward_config FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "own_autonomy_config" ON user_autonomy_config FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "read_reward_config" ON reward_config
    FOR SELECT USING (auth.role() = 'authenticated');

-- ── Seed Reward Config ────────────────────────────────────
INSERT INTO reward_config (module, event_type, reward_value, description) VALUES
    ('crm', 'lead_reply',      3.0,  'Lead replied to outreach'),
    ('crm', 'meeting_booked',  8.0,  'Meeting successfully booked'),
    ('crm', 'deal_closed',    21.0,  'Deal closed and won'),
    ('crm', 'no_response_7d', -4.0,  'No response after 7 days'),
    ('crm', 'lead_churn',    -10.0,  'Lead churned / lost'),
    ('marketing', 'ctr_increase',  5.0,  'Click-through rate increased'),
    ('marketing', 'cpa_decrease',  8.0,  'Cost per acquisition decreased'),
    ('marketing', 'conversion',   15.0,  'Campaign conversion recorded'),
    ('marketing', 'ad_fatigue',   -6.0,  'Ad fatigue detected'),
    ('marketing', 'budget_waste', -10.0, 'Budget waste detected'),
    ('shield', 'threat_blocked',       10.0, 'Security threat blocked'),
    ('shield', 'false_positive',       -3.0, 'False positive alert generated'),
    ('shield', 'data_misuse_detected', 15.0, 'Data misuse detected and flagged'),
    ('shield', 'breach',              -60.0, 'Security breach occurred'),
    ('website', 'page_conversion',     10.0, 'Visitor converted on page'),
    ('website', 'bounce',              -3.0, 'Visitor bounced without action'),
    ('website', 'session_value_high',   8.0, 'High-value session recorded'),
    ('website', 'core_vitals_improved', 5.0, 'Core Web Vitals improved'),
    ('neural-orbit', 'decision_applied',   5.0, 'AI decision was applied by user'),
    ('neural-orbit', 'decision_rejected', -2.0, 'AI decision was rejected by user'),
    ('neural-orbit', 'insight_acted_on',   8.0, 'AI insight was acted upon')
ON CONFLICT (module, event_type) DO NOTHING;
