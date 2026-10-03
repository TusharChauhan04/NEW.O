-- ============================================================
--  NeuralOrbit — Phase 2.5 Migration (Pre-Phase 3)
--  Adds: user_reward_config, user_autonomy_config tables
--  Patches: decisions table (override columns)
--
--  Run this in Supabase Dashboard → SQL Editor AFTER
--  running run_all_migrations.sql
-- ============================================================

-- ── 1. Patch decisions table with override columns ────────────
--  Adds human override tracking to the existing decisions table.
ALTER TABLE decisions
  ADD COLUMN IF NOT EXISTS override_enabled BOOLEAN DEFAULT false,
  ADD COLUMN IF NOT EXISTS override_by      TEXT;

CREATE INDEX IF NOT EXISTS idx_decisions_override
  ON decisions(override_enabled)
  WHERE override_enabled = true;

-- ── 2. user_reward_config ─────────────────────────────────────
--  Stores per-user reward weight slider settings.
--  One row per user (upserted by user_id).
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

ALTER TABLE user_reward_config ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "own_reward_config" ON user_reward_config;
CREATE POLICY "own_reward_config" ON user_reward_config
  FOR ALL USING (auth.uid() = user_id);

CREATE INDEX IF NOT EXISTS idx_user_reward_config_user
  ON user_reward_config(user_id);

-- ── 3. user_autonomy_config ───────────────────────────────────
--  Stores per-user autonomy level settings per module.
--  One row per user (upserted by user_id).
CREATE TABLE IF NOT EXISTS user_autonomy_config (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id        UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    global_level   TEXT NOT NULL DEFAULT 'assist'     CHECK (global_level   IN ('observe','assist','autonomous')),
    crm            TEXT NOT NULL DEFAULT 'assist'     CHECK (crm            IN ('observe','assist','autonomous')),
    marketing      TEXT NOT NULL DEFAULT 'assist'     CHECK (marketing      IN ('observe','assist','autonomous')),
    shield         TEXT NOT NULL DEFAULT 'observe'    CHECK (shield         IN ('observe','assist','autonomous')),
    website        TEXT NOT NULL DEFAULT 'autonomous' CHECK (website        IN ('observe','assist','autonomous')),
    locked_modules JSONB NOT NULL DEFAULT '[]',
    updated_by     TEXT,
    updated_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id)
);

ALTER TABLE user_autonomy_config ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "own_autonomy_config" ON user_autonomy_config;
CREATE POLICY "own_autonomy_config" ON user_autonomy_config
  FOR ALL USING (auth.uid() = user_id);

CREATE INDEX IF NOT EXISTS idx_user_autonomy_config_user
  ON user_autonomy_config(user_id);

-- ── 4. events: add sandbox flag ───────────────────────────────
--  Sandbox events don't trigger real AI actions.
ALTER TABLE events
  ADD COLUMN IF NOT EXISTS sandbox BOOLEAN DEFAULT false;

CREATE INDEX IF NOT EXISTS idx_events_sandbox
  ON events(sandbox)
  WHERE sandbox = true;

-- ── 5. Trigger: auto-update updated_at on config changes ──────
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
