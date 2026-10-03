-- ============================================================
-- Phase 4 Milestone 1 — AI Learning Stats Table
-- NeuralOrbit: learning_stats migration
--
-- Run this once in Supabase SQL Editor:
-- Dashboard → SQL Editor → New Query → Paste → Run
--
-- SAFE: Only creates a new table. Does NOT touch any existing table.
-- ============================================================

CREATE TABLE IF NOT EXISTS learning_stats (
    id                  UUID            DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id             UUID            NOT NULL,
    module              TEXT            NOT NULL,

    -- Decision counters
    total_decisions     INTEGER         DEFAULT 0,
    correct_decisions   INTEGER         DEFAULT 0,
    rejected_decisions  INTEGER         DEFAULT 0,

    -- Computed metrics
    accuracy_pct        FLOAT           DEFAULT 0.0,
    avg_confidence      FLOAT           DEFAULT 0.0,

    -- Timestamps
    last_decision_at    TIMESTAMPTZ,
    updated_at          TIMESTAMPTZ     DEFAULT NOW(),
    created_at          TIMESTAMPTZ     DEFAULT NOW(),

    -- One row per user per module
    UNIQUE (user_id, module)
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_learning_stats_user_id
    ON learning_stats (user_id);

CREATE INDEX IF NOT EXISTS idx_learning_stats_module
    ON learning_stats (user_id, module);

-- Row Level Security
ALTER TABLE learning_stats ENABLE ROW LEVEL SECURITY;

-- Drop policies first so this script is safe to re-run
DROP POLICY IF EXISTS "Users can read own learning stats"   ON learning_stats;
DROP POLICY IF EXISTS "Users can insert own learning stats" ON learning_stats;
DROP POLICY IF EXISTS "Users can update own learning stats" ON learning_stats;

CREATE POLICY "Users can read own learning stats"
    ON learning_stats FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own learning stats"
    ON learning_stats FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own learning stats"
    ON learning_stats FOR UPDATE
    USING (auth.uid() = user_id);

-- ============================================================
-- DONE. Table is ready.
-- The backend writes here every time a user approves/rejects
-- a decision in the Decision Log.
-- ============================================================
