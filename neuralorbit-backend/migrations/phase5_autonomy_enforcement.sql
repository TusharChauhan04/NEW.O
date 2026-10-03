-- =============================================================================
-- Phase 5: Autonomy Enforcement — New columns on decisions table
-- ADDITIVE: Only adds new columns with defaults. No existing column modified.
-- Safe to run on existing data — all existing rows get FALSE defaults.
-- =============================================================================

-- Track whether a decision was auto-executed by Autonomous mode
ALTER TABLE decisions ADD COLUMN IF NOT EXISTS auto_executed BOOLEAN DEFAULT FALSE;

-- Track whether a decision is Observe-only (admin sees, user does not)
ALTER TABLE decisions ADD COLUMN IF NOT EXISTS observe_only BOOLEAN DEFAULT FALSE;

-- Performance indexes for admin queries filtering by these new flags
CREATE INDEX IF NOT EXISTS idx_decisions_auto_executed ON decisions(auto_executed) WHERE auto_executed = TRUE;
CREATE INDEX IF NOT EXISTS idx_decisions_observe_only  ON decisions(observe_only)  WHERE observe_only  = TRUE;
