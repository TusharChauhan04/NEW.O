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
--  NeuralOrbit Backend — Supabase Database Schema (Phase 1)
--  Run this ONCE in your Supabase Dashboard → SQL Editor
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";   -- pgvector (ready for Phase 2)

-- ── events ──────────────────────────────────────────────────────────────────
-- Central event tracker — every business action is logged here
CREATE TABLE IF NOT EXISTS events (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    module      TEXT NOT NULL,      -- 'crm' | 'marketing' | 'shield' | 'website' | 'neural-orbit'
    event_type  TEXT NOT NULL,      -- 'lead_reply' | 'meeting_booked' | 'threat_blocked' | ...
    payload     JSONB DEFAULT '{}', -- Flexible event-specific data
    context     JSONB DEFAULT '{}', -- Environmental state at time of event
    source      TEXT DEFAULT 'api', -- 'manual' | 'n8n' | 'api' | 'system'
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── decisions ────────────────────────────────────────────────────────────────
-- AI Decision Log — stores every recommendation + its outcome
CREATE TABLE IF NOT EXISTS decisions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    module          TEXT NOT NULL,
    action          TEXT NOT NULL,          -- What the AI decided
    reasoning       TEXT,                   -- Why
    confidence      FLOAT,                  -- 0.0 → 1.0
    state_snapshot  JSONB DEFAULT '{}',     -- System state at decision time
    alternatives    JSONB DEFAULT '[]',     -- Other options considered
    outcome         TEXT DEFAULT 'pending', -- 'applied' | 'rejected' | 'pending'
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── rewards ──────────────────────────────────────────────────────────────────
-- Reward ledger — every scored event creates a record here
CREATE TABLE IF NOT EXISTS rewards (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id      UUID REFERENCES events(id) ON DELETE SET NULL,
    decision_id   UUID REFERENCES decisions(id) ON DELETE SET NULL,
    user_id       UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    module        TEXT NOT NULL,
    event_type    TEXT NOT NULL,
    reward_value  FLOAT NOT NULL,             -- Positive or negative score
    reward_source TEXT DEFAULT 'rule_engine', -- 'rule_engine' | 'manual' | 'llm'
    notes         TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ── reward_config ────────────────────────────────────────────────────────────
-- Editable reward rules — seeded from your Reward Frameworks document
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

-- ── module_states ─────────────────────────────────────────────────────────────
-- Current AI state per user per module — running totals + custom state JSONB
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

-- ── memory_vectors ───────────────────────────────────────────────────────────
-- Phase 2: Vector memory for AI long-term learning
-- (Table created now, populated in Phase 2)
CREATE TABLE IF NOT EXISTS memory_vectors (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    module      TEXT NOT NULL,
    content     TEXT NOT NULL,
    embedding   vector(1536),     -- OpenAI embedding dimension
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── bandit_arms ──────────────────────────────────────────────────────────────
-- Phase 2: Multi-Armed Bandit state (Thompson Sampling)
CREATE TABLE IF NOT EXISTS bandit_arms (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    module      TEXT NOT NULL,
    arm_key     TEXT NOT NULL,  -- Action identifier
    alpha       FLOAT DEFAULT 1.0,  -- Successes (Beta distribution)
    beta        FLOAT DEFAULT 1.0,  -- Failures
    total_pulls INT DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, module, arm_key)
);

-- ── Indexes ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_events_user_module   ON events(user_id, module);
CREATE INDEX IF NOT EXISTS idx_events_created_at    ON events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_decisions_user_module ON decisions(user_id, module);
CREATE INDEX IF NOT EXISTS idx_rewards_user_module  ON rewards(user_id, module);
CREATE INDEX IF NOT EXISTS idx_rewards_created_at   ON rewards(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memory_user_module   ON memory_vectors(user_id, module);
-- pgvector HNSW index for fast similarity search (Phase 2)
CREATE INDEX IF NOT EXISTS idx_memory_embedding
    ON memory_vectors USING hnsw (embedding vector_cosine_ops);

-- ── Row Level Security ────────────────────────────────────────────────────────
ALTER TABLE events         ENABLE ROW LEVEL SECURITY;
ALTER TABLE decisions      ENABLE ROW LEVEL SECURITY;
ALTER TABLE rewards        ENABLE ROW LEVEL SECURITY;
ALTER TABLE module_states  ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_vectors ENABLE ROW LEVEL SECURITY;
ALTER TABLE bandit_arms    ENABLE ROW LEVEL SECURITY;
ALTER TABLE reward_config  ENABLE ROW LEVEL SECURITY;

-- Users see only their own data
CREATE POLICY "own_events"   ON events         FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "own_decisions" ON decisions     FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "own_rewards"  ON rewards        FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "own_states"   ON module_states  FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "own_memory"   ON memory_vectors FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "own_bandits"  ON bandit_arms    FOR ALL USING (auth.uid() = user_id);

-- reward_config: all authenticated users can read; only service role can write
CREATE POLICY "read_reward_config" ON reward_config
    FOR SELECT USING (auth.role() = 'authenticated');

-- ── Seed: Reward Configuration ────────────────────────────────────────────────
-- From your "Reward Frameworks (CORE IP)" document
INSERT INTO reward_config (module, event_type, reward_value, description) VALUES
    -- CRM Module
    ('crm', 'lead_reply',      3.0,  'Lead replied to outreach'),
    ('crm', 'meeting_booked',  8.0,  'Meeting successfully booked'),
    ('crm', 'deal_closed',    21.0,  'Deal closed and won'),
    ('crm', 'no_response_7d', -4.0,  'No response after 7 days'),
    ('crm', 'lead_churn',    -10.0,  'Lead churned / lost'),

    -- Marketing Module
    ('marketing', 'ctr_increase',  5.0,  'Click-through rate increased'),
    ('marketing', 'cpa_decrease',  8.0,  'Cost per acquisition decreased'),
    ('marketing', 'conversion',   15.0,  'Campaign conversion recorded'),
    ('marketing', 'ad_fatigue',   -6.0,  'Ad fatigue detected'),
    ('marketing', 'budget_waste', -10.0, 'Budget waste detected'),

    -- Shield Module
    ('shield', 'threat_blocked',        10.0,  'Security threat blocked'),
    ('shield', 'false_positive',        -3.0,  'False positive alert generated'),
    ('shield', 'data_misuse_detected',  15.0,  'Data misuse detected and flagged'),
    ('shield', 'breach',               -60.0,  'Security breach occurred'),

    -- Website Module
    ('website', 'page_conversion',      10.0, 'Visitor converted on page'),
    ('website', 'bounce',               -3.0, 'Visitor bounced without action'),
    ('website', 'session_value_high',    8.0, 'High-value session recorded'),
    ('website', 'core_vitals_improved',  5.0, 'Core Web Vitals improved'),

    -- NeuralOrbit (master module)
    ('neural-orbit', 'decision_applied',   5.0, 'AI decision was applied by user'),
    ('neural-orbit', 'decision_rejected', -2.0, 'AI decision was rejected by user'),
    ('neural-orbit', 'insight_acted_on',   8.0, 'AI insight was acted upon')

ON CONFLICT (module, event_type) DO NOTHING;
