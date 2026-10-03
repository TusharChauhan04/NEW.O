-- =============================================================================
-- Phase 6: Structured action codes on decisions
-- ADDITIVE: one nullable column. No existing column modified, no data touched.
--
-- WHY: the n8n executor (executor.py) matches on (module, action_code) using
-- a fixed registry of short codes like "assign_lead". Every decision-writing
-- path (the rule-based generator and the LLM recommender) previously wrote
-- only a free-text sentence as `action` — those never matched the registry,
-- so POST /decisions/{id}/execute returned "no_webhook" for every decision
-- that was ever actually generated. Both writers now also populate
-- action_code; older rows will simply have action_code = NULL, which the
-- executor already handles as "not executable via n8n" (unchanged behavior
-- for pre-existing rows).
-- =============================================================================

ALTER TABLE decisions ADD COLUMN IF NOT EXISTS action_code TEXT;

CREATE INDEX IF NOT EXISTS idx_decisions_action_code
  ON decisions(module, action_code)
  WHERE action_code IS NOT NULL;
