-- =============================================================================
--  Phase 7: Performance indexes
--
--  ADDITIVE AND NON-DESTRUCTIVE. Creates indexes only — no table, column, or
--  row is modified. Safe to re-run (every statement is IF NOT EXISTS).
--
--  Each index below was derived by comparing the columns actually used in
--  .eq()/.order()/.gte() filters across app/ against the indexes defined in
--  000_baseline_schema.sql. Four gaps were found where a hot query had no
--  supporting index.
--
--  NOTE ON CONCURRENTLY: `CREATE INDEX CONCURRENTLY` cannot run inside a
--  transaction block. The Supabase SQL Editor wraps statements in one, so the
--  plain form is used here — it takes a brief write lock on the table, which is
--  acceptable at current data volumes. If these tables have grown large by the
--  time you run this, execute each statement separately via psql with
--  CONCURRENTLY added.
--
--  VERIFY BEFORE AND AFTER with EXPLAIN ANALYZE, e.g.:
--    EXPLAIN ANALYZE SELECT * FROM decisions ORDER BY created_at DESC LIMIT 50;
--  Expect: "Seq Scan + Sort" before, "Index Scan Backward" after.
-- =============================================================================

-- ── 1. decisions(created_at DESC) ────────────────────────────────────────────
-- `decisions` had NO index on created_at, yet api/v1/decisions.py orders by it
-- on every load: .order("created_at", desc=True).limit(50). For an admin
-- (no user_id filter) that is a full table sort on the admin decision log —
-- the most frequently opened admin page.
CREATE INDEX IF NOT EXISTS idx_decisions_created_at
    ON decisions (created_at DESC);

-- ── 2. decisions(outcome, created_at DESC) ───────────────────────────────────
-- `outcome` is unindexed. api/v1/analytics.py and learning_engine.py filter
-- outcome='rejected' then sort by created_at — currently a full scan plus sort
-- to return ~10 rows.
CREATE INDEX IF NOT EXISTS idx_decisions_outcome_created
    ON decisions (outcome, created_at DESC);

-- ── 3. events(user_id, module, event_type, created_at) ───────────────────────
-- idx_events_user_module stops at (user_id, module), so each trigger check in
-- decision_generator.py heap-filters on event_type + created_at across that
-- user's entire module history. This runs ~6x per user per hour.
CREATE INDEX IF NOT EXISTS idx_events_user_module_type_created
    ON events (user_id, module, event_type, created_at DESC);

-- ── 4. integrations(webhook_secret) ──────────────────────────────────────────
-- api/v1/tracking.py::_resolve_token looks up by webhook_secret on the public,
-- unauthenticated /track path. Unindexed, this is a sequential scan on the
-- highest-traffic endpoint in the system.
CREATE INDEX IF NOT EXISTS idx_integrations_webhook_secret
    ON integrations (webhook_secret)
    WHERE webhook_secret IS NOT NULL;

-- ── Record it ────────────────────────────────────────────────────────────────
INSERT INTO schema_migrations (version, note) VALUES
    ('007_performance_indexes', 'Indexes for decision log sort, outcome filter, trigger checks, tracker token lookup')
ON CONFLICT (version) DO NOTHING;

-- =============================================================================
--  Verify:
--    SELECT indexname FROM pg_indexes
--     WHERE tablename IN ('decisions','events','integrations')
--     ORDER BY tablename, indexname;
-- =============================================================================
