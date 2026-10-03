-- =============================================================================
-- Phase 5: AI Brain — Mistake Pattern Memory
-- ADDITIVE: Brand new table. No existing table is touched.
-- =============================================================================

CREATE TABLE IF NOT EXISTS mistake_patterns (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id          UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    module           TEXT        NOT NULL,
    trigger_type     TEXT        NOT NULL,  -- e.g. "high_bounce_rate", "no_activity_5d"
    bad_action       TEXT        NOT NULL,  -- the action string the AI recommended
    context_snapshot JSONB       DEFAULT '{}',
    times_rejected   INT         DEFAULT 1,
    last_seen_at     TIMESTAMPTZ DEFAULT NOW(),
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    -- Unique constraint: same user + module + trigger + action = one row (upserted)
    UNIQUE(user_id, module, trigger_type, bad_action)
);

-- RLS: users can read their own patterns; service role has full access
-- SECURITY FIX: the service-role policy previously had no `TO service_role`
-- clause, so in Postgres it applied to PUBLIC (every role, not just the
-- service role). Since permissive policies are OR'd together, that made
-- `USING (true)` win for every request regardless of role — any authenticated
-- (or anon) caller could read/write every tenant's rows. Re-run this file
-- against the live database to apply the fix (DROP+CREATE is idempotent).
ALTER TABLE mistake_patterns ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users see own mistake patterns" ON mistake_patterns;
DROP POLICY IF EXISTS "Service role full access to mistake patterns" ON mistake_patterns;

CREATE POLICY "Users see own mistake patterns"
    ON mistake_patterns FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Service role full access to mistake patterns"
    ON mistake_patterns FOR ALL
    TO service_role
    USING (true) WITH CHECK (true);

-- Index for fast per-user-module lookups (used by LLM prompt builder)
CREATE INDEX IF NOT EXISTS idx_mistake_patterns_user_module
    ON mistake_patterns(user_id, module);

-- Index for admin cross-user queries (most-rejected patterns across all users)
CREATE INDEX IF NOT EXISTS idx_mistake_patterns_times_rejected
    ON mistake_patterns(times_rejected DESC);
