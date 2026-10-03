-- =============================================================================
--  NeuralOrbit — CANONICAL BASELINE SCHEMA
--
--  This single file replaces three overlapping, drifted scripts:
--      scripts/init_db.sql            (7 tables, no integrations)
--      scripts/setup_complete.sql     (12 tables)
--      scripts/run_all_migrations.sql (10 tables, DIFFERENT unique constraint)
--  Those three are now deprecated. See migrations/README.md.
--
--  SAFETY CONTRACT — this file is safe to run against a LIVE database:
--    * Every CREATE is `IF NOT EXISTS`      -> no-op if the object exists
--    * Every column add is `ADD COLUMN IF NOT EXISTS`
--    * There is NO DROP TABLE and NO DELETE anywhere in this file
--    * The one constraint change (see §12) only WIDENS a uniqueness rule,
--      which cannot fail on existing rows
--  Running it twice is harmless. Running it on a fresh project builds
--  everything from scratch.
-- =============================================================================

-- ── 1. Extensions ────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ── 2. Migration tracking (new) ──────────────────────────────────────────────
-- Previously there was no way to tell which scripts had been applied to a
-- given database. That is exactly how the three setup scripts drifted apart.
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    note        TEXT
);

-- ── 3. events ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS events (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id      UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    module       TEXT NOT NULL,
    event_type   TEXT NOT NULL,
    payload      JSONB DEFAULT '{}',
    context      JSONB DEFAULT '{}',
    source       TEXT DEFAULT 'api',
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
-- Columns added by later phases (tracker reward scoring, sandbox mode):
ALTER TABLE events ADD COLUMN IF NOT EXISTS reward_value FLOAT DEFAULT 0;
ALTER TABLE events ADD COLUMN IF NOT EXISTS sandbox BOOLEAN DEFAULT false;

-- ── 4. decisions ─────────────────────────────────────────────────────────────
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
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
-- Phase 2.5: human override tracking
ALTER TABLE decisions ADD COLUMN IF NOT EXISTS override_enabled BOOLEAN DEFAULT false;
ALTER TABLE decisions ADD COLUMN IF NOT EXISTS override_by      TEXT;
-- Phase 5: autonomy enforcement flags
ALTER TABLE decisions ADD COLUMN IF NOT EXISTS auto_executed    BOOLEAN DEFAULT false;
ALTER TABLE decisions ADD COLUMN IF NOT EXISTS observe_only     BOOLEAN DEFAULT false;
-- Phase 6: structured action code for the n8n executor
ALTER TABLE decisions ADD COLUMN IF NOT EXISTS action_code      TEXT;

-- ── 5. rewards ───────────────────────────────────────────────────────────────
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

-- ── 6. reward_config ─────────────────────────────────────────────────────────
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

-- ── 7. module_states ─────────────────────────────────────────────────────────
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

-- ── 8. Forward-looking tables (schema only; nothing writes to these yet) ──────
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

-- ── 9. profiles (RBAC source of truth) ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.profiles (
    id          UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name   TEXT,
    company     TEXT,
    plan        TEXT NOT NULL DEFAULT 'starter',
    role        TEXT NOT NULL DEFAULT 'user',
    avatar_url  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── 10. Per-user config ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_reward_config (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    conversion  INT  NOT NULL DEFAULT 75,
    retention   INT  NOT NULL DEFAULT 85,
    cost        INT  NOT NULL DEFAULT 40,
    risk        INT  NOT NULL DEFAULT 30,
    industry    TEXT NOT NULL DEFAULT 'SaaS',
    sim_mode    BOOLEAN NOT NULL DEFAULT true,
    updated_by  TEXT,
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id)
);

CREATE TABLE IF NOT EXISTS user_autonomy_config (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id        UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    global_level   TEXT NOT NULL DEFAULT 'assist'     CHECK (global_level IN ('observe','assist','autonomous')),
    crm            TEXT NOT NULL DEFAULT 'assist'     CHECK (crm         IN ('observe','assist','autonomous')),
    marketing      TEXT NOT NULL DEFAULT 'assist'     CHECK (marketing   IN ('observe','assist','autonomous')),
    shield         TEXT NOT NULL DEFAULT 'observe'    CHECK (shield      IN ('observe','assist','autonomous')),
    website        TEXT NOT NULL DEFAULT 'autonomous' CHECK (website     IN ('observe','assist','autonomous')),
    locked_modules JSONB NOT NULL DEFAULT '[]',
    updated_by     TEXT,
    updated_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id)
);

-- ── 11. AI learning / memory ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS learning_stats (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id            UUID NOT NULL,
    module             TEXT NOT NULL,
    total_decisions    INTEGER DEFAULT 0,
    correct_decisions  INTEGER DEFAULT 0,
    rejected_decisions INTEGER DEFAULT 0,
    accuracy_pct       FLOAT   DEFAULT 0.0,
    avg_confidence     FLOAT   DEFAULT 0.0,
    last_decision_at   TIMESTAMPTZ,
    updated_at         TIMESTAMPTZ DEFAULT NOW(),
    created_at         TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, module)
);

CREATE TABLE IF NOT EXISTS mistake_patterns (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id          UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    module           TEXT NOT NULL,
    trigger_type     TEXT NOT NULL,
    bad_action       TEXT NOT NULL,
    context_snapshot JSONB DEFAULT '{}',
    times_rejected   INT DEFAULT 1,
    last_seen_at     TIMESTAMPTZ DEFAULT NOW(),
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, module, trigger_type, bad_action)
);

-- ── 12. Integrations ─────────────────────────────────────────────────────────
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
ALTER TABLE integrations ADD COLUMN IF NOT EXISTS webhook_secret TEXT;

-- RESOLVE THE DRIFT.
-- run_all_migrations.sql created UNIQUE (user_id, module, platform) — without
-- `label`. That caps a tenant at ONE integration per platform per module, but
-- the app assigns a label per integration and expects several. The other two
-- scripts include `label`, which is correct.
--
-- This block is safe: replacing the 3-column key with the 4-column key only
-- LOOSENS uniqueness, so it cannot conflict with rows already stored.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'integrations'::regclass
          AND conname  = 'integrations_user_id_module_platform_key'
    ) THEN
        ALTER TABLE integrations
            DROP CONSTRAINT integrations_user_id_module_platform_key;
        RAISE NOTICE 'Dropped narrow 3-column unique constraint on integrations.';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'integrations'::regclass
          AND conname  = 'integrations_user_id_module_platform_label_key'
    ) THEN
        ALTER TABLE integrations
            ADD CONSTRAINT integrations_user_id_module_platform_label_key
            UNIQUE (user_id, module, platform, label);
        RAISE NOTICE 'Added 4-column unique constraint (incl. label) on integrations.';
    END IF;
END $$;

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
ALTER TABLE integration_api_keys ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true;

CREATE TABLE IF NOT EXISTS raw_integration_events (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    integration_id  UUID REFERENCES integrations(id) ON DELETE CASCADE,
    user_id         UUID REFERENCES auth.users(id),
    platform        TEXT,
    raw_payload     JSONB NOT NULL,
    normalized      BOOLEAN DEFAULT false,
    error           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
-- Reconcile the two column variants that existed across scripts:
ALTER TABLE raw_integration_events ADD COLUMN IF NOT EXISTS platform   TEXT;
ALTER TABLE raw_integration_events ADD COLUMN IF NOT EXISTS normalized BOOLEAN DEFAULT false;
ALTER TABLE raw_integration_events ADD COLUMN IF NOT EXISTS headers    JSONB DEFAULT '{}';
ALTER TABLE raw_integration_events ADD COLUMN IF NOT EXISTS processed  BOOLEAN DEFAULT false;

-- ── 13. Indexes ──────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_events_user_module        ON events(user_id, module);
CREATE INDEX IF NOT EXISTS idx_events_created_at         ON events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_decisions_user_module     ON decisions(user_id, module);
CREATE INDEX IF NOT EXISTS idx_rewards_user_module       ON rewards(user_id, module);
CREATE INDEX IF NOT EXISTS idx_rewards_created_at        ON rewards(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_profiles_role             ON public.profiles(role);
CREATE INDEX IF NOT EXISTS idx_integrations_user         ON integrations(user_id);
CREATE INDEX IF NOT EXISTS idx_integrations_module       ON integrations(user_id, module);
CREATE INDEX IF NOT EXISTS idx_api_keys_hash             ON integration_api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_raw_events_integration    ON raw_integration_events(integration_id);
CREATE INDEX IF NOT EXISTS idx_learning_stats_module     ON learning_stats(user_id, module);
CREATE INDEX IF NOT EXISTS idx_mistake_patterns_user_mod ON mistake_patterns(user_id, module);
CREATE INDEX IF NOT EXISTS idx_decisions_action_code     ON decisions(module, action_code) WHERE action_code IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_decisions_override        ON decisions(override_enabled)    WHERE override_enabled = true;
CREATE INDEX IF NOT EXISTS idx_events_sandbox            ON events(sandbox)                WHERE sandbox = true;

-- ── 14. Row Level Security ───────────────────────────────────────────────────
ALTER TABLE events                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE decisions              ENABLE ROW LEVEL SECURITY;
ALTER TABLE rewards                ENABLE ROW LEVEL SECURITY;
ALTER TABLE module_states          ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_vectors         ENABLE ROW LEVEL SECURITY;
ALTER TABLE bandit_arms            ENABLE ROW LEVEL SECURITY;
ALTER TABLE reward_config          ENABLE ROW LEVEL SECURITY;
ALTER TABLE integrations           ENABLE ROW LEVEL SECURITY;
ALTER TABLE integration_api_keys   ENABLE ROW LEVEL SECURITY;
ALTER TABLE raw_integration_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_reward_config     ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_autonomy_config   ENABLE ROW LEVEL SECURITY;
ALTER TABLE learning_stats         ENABLE ROW LEVEL SECURITY;
ALTER TABLE mistake_patterns       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profiles        ENABLE ROW LEVEL SECURITY;

-- Policies are DROP+CREATE so this file stays re-runnable.
DROP POLICY IF EXISTS "own_events"          ON events;
DROP POLICY IF EXISTS "own_decisions"       ON decisions;
DROP POLICY IF EXISTS "own_rewards"         ON rewards;
DROP POLICY IF EXISTS "own_states"          ON module_states;
DROP POLICY IF EXISTS "own_memory"          ON memory_vectors;
DROP POLICY IF EXISTS "own_bandits"         ON bandit_arms;
DROP POLICY IF EXISTS "read_reward_config"  ON reward_config;
DROP POLICY IF EXISTS "own_integrations"    ON integrations;
DROP POLICY IF EXISTS "own_api_keys"        ON integration_api_keys;
DROP POLICY IF EXISTS "own_raw_events"      ON raw_integration_events;
DROP POLICY IF EXISTS "own_reward_config"   ON user_reward_config;
DROP POLICY IF EXISTS "own_autonomy_config" ON user_autonomy_config;

CREATE POLICY "own_events"          ON events                 FOR ALL    USING (auth.uid() = user_id);
CREATE POLICY "own_decisions"       ON decisions              FOR ALL    USING (auth.uid() = user_id);
CREATE POLICY "own_rewards"         ON rewards                FOR ALL    USING (auth.uid() = user_id);
CREATE POLICY "own_states"          ON module_states          FOR ALL    USING (auth.uid() = user_id);
CREATE POLICY "own_memory"          ON memory_vectors         FOR ALL    USING (auth.uid() = user_id);
CREATE POLICY "own_bandits"         ON bandit_arms            FOR ALL    USING (auth.uid() = user_id);
CREATE POLICY "own_integrations"    ON integrations           FOR ALL    USING (auth.uid() = user_id);
CREATE POLICY "own_api_keys"        ON integration_api_keys   FOR ALL    USING (auth.uid() = user_id);
CREATE POLICY "own_raw_events"      ON raw_integration_events FOR ALL    USING (auth.uid() = user_id);
CREATE POLICY "own_reward_config"   ON user_reward_config     FOR ALL    USING (auth.uid() = user_id);
CREATE POLICY "own_autonomy_config" ON user_autonomy_config   FOR ALL    USING (auth.uid() = user_id);
CREATE POLICY "read_reward_config"  ON reward_config          FOR SELECT USING (auth.role() = 'authenticated');

-- learning_stats: own rows only
DROP POLICY IF EXISTS "Users can read own learning stats"   ON learning_stats;
DROP POLICY IF EXISTS "Users can insert own learning stats" ON learning_stats;
DROP POLICY IF EXISTS "Users can update own learning stats" ON learning_stats;
CREATE POLICY "Users can read own learning stats"   ON learning_stats FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own learning stats" ON learning_stats FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own learning stats" ON learning_stats FOR UPDATE USING (auth.uid() = user_id);

-- mistake_patterns: NOTE the `TO service_role` clause. Without it the
-- service-role policy applies to PUBLIC, and because permissive policies are
-- OR'd together, `USING (true)` would win for every role and disable RLS on
-- this table entirely.
DROP POLICY IF EXISTS "Users see own mistake patterns"                ON mistake_patterns;
DROP POLICY IF EXISTS "Service role full access to mistake patterns"  ON mistake_patterns;
CREATE POLICY "Users see own mistake patterns"
    ON mistake_patterns FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Service role full access to mistake patterns"
    ON mistake_patterns FOR ALL TO service_role USING (true) WITH CHECK (true);

-- profiles: own row readable/updatable; backend (service role) reads all.
DROP POLICY IF EXISTS "own_profile_read"  ON public.profiles;
DROP POLICY IF EXISTS "own_profile_write" ON public.profiles;
DROP POLICY IF EXISTS "service_role_all"  ON public.profiles;
CREATE POLICY "own_profile_read"  ON public.profiles FOR SELECT USING (auth.uid() = id);
CREATE POLICY "own_profile_write" ON public.profiles FOR UPDATE USING (auth.uid() = id);
CREATE POLICY "service_role_all"  ON public.profiles FOR ALL TO service_role USING (true) WITH CHECK (true);

-- SECURITY: an RLS policy scopes WHICH ROW, never WHICH COLUMNS. The
-- own_profile_write policy above therefore let a user PATCH their own
-- profiles row — including `role` — straight through PostgREST with their
-- own valid JWT:
--     PATCH /rest/v1/profiles?id=eq.<own-uid>   {"role":"admin"}
-- RLS approves it (it IS their row), and is_admin_user() then reads that
-- value as the source of truth. Self-promotion to platform admin.
--
-- Column-level REVOKE is the fix: row access stays, column access does not.
-- The backend uses the service-role key, which is exempt, so
-- PATCH /api/v1/profile/admin/{user_id} (gated by get_admin_user) keeps
-- working as the one legitimate promotion path.
REVOKE UPDATE (role, plan) ON public.profiles FROM authenticated;
REVOKE UPDATE (role, plan) ON public.profiles FROM anon;

-- Defence in depth: even if the grants above are ever restored by hand, this
-- trigger rejects any non-service-role attempt to change role or plan.
CREATE OR REPLACE FUNCTION public.prevent_self_privilege_escalation()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    IF current_setting('request.jwt.claim.role', true) IS DISTINCT FROM 'service_role' THEN
        IF NEW.role IS DISTINCT FROM OLD.role THEN
            RAISE EXCEPTION 'profiles.role may only be changed by the service role';
        END IF;
        IF NEW.plan IS DISTINCT FROM OLD.plan THEN
            RAISE EXCEPTION 'profiles.plan may only be changed by the service role';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_prevent_privilege_escalation ON public.profiles;
CREATE TRIGGER trg_prevent_privilege_escalation
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW EXECUTE FUNCTION public.prevent_self_privilege_escalation();

-- ── 15. Auto-create a profile row on signup ──────────────────────────────────
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO public.profiles (id, full_name, company, role)
    VALUES (
        NEW.id,
        COALESCE(NEW.raw_user_meta_data->>'name', NEW.email),
        COALESCE(NEW.raw_user_meta_data->>'company', NULL),
        -- SECURITY: role is HARDCODED to 'user' and must never be read from
        -- raw_user_meta_data. That column is the `options.data` blob the
        -- client passes to supabase.auth.signUp(), so it is fully attacker-
        -- controlled: signUp({options:{data:{role:'admin'}}}) would otherwise
        -- write role='admin' straight into the table that is_admin_user()
        -- treats as the sole source of truth — self-service admin from the
        -- public anon key.
        -- Promotions go exclusively through PATCH /profile/admin/{user_id},
        -- which is gated by get_admin_user and validates the value.
        'user'
    )
    ON CONFLICT (id) DO NOTHING;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Backfill profiles for users who signed up before the trigger existed.
-- SECURITY: same reasoning as the trigger above — role is hardcoded, never
-- sourced from the user-controlled metadata blob.
INSERT INTO public.profiles (id, full_name, company, role, created_at)
SELECT id,
       COALESCE(raw_user_meta_data->>'name', email),
       raw_user_meta_data->>'company',
       'user',
       created_at
FROM auth.users
ON CONFLICT (id) DO NOTHING;

-- ── 16. updated_at trigger for config tables ─────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_reward_config_updated_at ON user_reward_config;
CREATE TRIGGER trg_reward_config_updated_at
    BEFORE UPDATE ON user_reward_config
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS trg_autonomy_config_updated_at ON user_autonomy_config;
CREATE TRIGGER trg_autonomy_config_updated_at
    BEFORE UPDATE ON user_autonomy_config
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── 17. Seed reward configuration ────────────────────────────────────────────
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
    ('website', 'page_conversion',      10.0, 'Visitor converted on page'),
    ('website', 'bounce',               -3.0, 'Visitor bounced without action'),
    ('website', 'session_value_high',    8.0, 'High-value session recorded'),
    ('website', 'core_vitals_improved',  5.0, 'Core Web Vitals improved'),
    ('website', 'page_view',             1.0, 'Page view tracked by tracker.js'),
    ('website', 'form_submit',          10.0, 'Form submitted via tracker.js'),
    ('website', 'engaged_session',       8.0, 'Engaged session (>30s)'),
    ('neural-orbit', 'decision_applied',   5.0, 'AI decision was applied by user'),
    ('neural-orbit', 'decision_rejected', -2.0, 'AI decision was rejected by user'),
    ('neural-orbit', 'insight_acted_on',   8.0, 'AI insight was acted upon')
ON CONFLICT (module, event_type) DO NOTHING;

-- ── 18. Record this baseline (and the phases it subsumes) ────────────────────
INSERT INTO schema_migrations (version, note) VALUES
    ('000_baseline_schema',           'Canonical consolidated schema'),
    ('add_profiles',                  'subsumed by baseline'),
    ('phase2_5_migration',            'subsumed by baseline'),
    ('phase4_learning_stats',         'subsumed by baseline'),
    ('phase5_autonomy_enforcement',   'subsumed by baseline'),
    ('phase5_mistake_patterns',       'subsumed by baseline (incl. TO service_role fix)'),
    ('phase6_action_codes',           'subsumed by baseline')
ON CONFLICT (version) DO NOTHING;

-- =============================================================================
--  DONE. Verify with:
--    SELECT version, applied_at FROM schema_migrations ORDER BY version;
--    SELECT conname FROM pg_constraint
--     WHERE conrelid = 'integrations'::regclass AND contype = 'u';
-- =============================================================================
