-- =============================================================================
--  Phase 5 (C1): Reconcile reward_config with the event types writers emit
--
--  ADDITIVE AND NON-DESTRUCTIVE. INSERT ... ON CONFLICT DO NOTHING only.
--  No row is updated or deleted, so any value an admin has already tuned is
--  preserved. Safe to re-run.
--
--  WHY
--  All four ingest paths now run the shared reward pipeline
--  (reward_engine.record_event). That pipeline resolves a reward from this
--  table first. But an audit of what the writers actually emit against what
--  was seeded found ~19 event types with NO matching row:
--
--    website : cta_click, checkout_complete, scroll_depth_full,
--              scroll_depth_high, session_engaged, session_bounce, session_end
--    crm     : proposal_sent, follow_up_completed, lead_created,
--              lead_qualified, lead_assigned, contact_created,
--              deal_updated, deal_lost
--
--  Two of those are pure naming drift — the table was seeded with
--  'engaged_session' and 'bounce' while the tracker emits 'session_engaged'
--  and 'session_bounce' (note the reversed word order). seed_test_data.sql
--  agrees with the TRACKER, which confirms the table is the outlier.
--
--  The values below are taken verbatim from the hardcoded maps they replace
--  (tracking._REWARD_MAP and normalizers.crm.CRM_REWARD_MAP), so effective
--  reward values do not change — this only moves them under admin control.
--
--  The old 'engaged_session' and 'bounce' rows are intentionally LEFT IN
--  PLACE. Nothing emits those names, so they are inert; deleting rows is
--  destructive and buys nothing.
-- =============================================================================

INSERT INTO reward_config (module, event_type, reward_value, description) VALUES
    -- ── website (values from tracking._REWARD_MAP) ───────────────────────────
    ('website', 'cta_click',          3.0,  'CTA clicked (tracker.js)'),
    ('website', 'checkout_complete', 15.0,  'Checkout completed (tracker.js)'),
    ('website', 'scroll_depth_high',  4.0,  'Scrolled past 75% of page'),
    ('website', 'scroll_depth_full',  6.0,  'Scrolled to 100% of page'),
    ('website', 'session_engaged',    8.0,  'Engaged session (>300s) — replaces engaged_session'),
    ('website', 'session_bounce',    -3.0,  'Bounced session (<10s) — replaces bounce'),
    ('website', 'session_end',        0.5,  'Ordinary session end'),

    -- ── crm (values from normalizers.crm.CRM_REWARD_MAP) ─────────────────────
    ('crm', 'proposal_sent',        5.0,  'Proposal sent to lead'),
    ('crm', 'follow_up_completed',  3.0,  'Follow-up task completed'),
    ('crm', 'lead_created',         2.0,  'New lead created'),
    ('crm', 'lead_qualified',       5.0,  'Lead qualified'),
    ('crm', 'lead_assigned',        1.0,  'Lead assigned to an owner'),
    ('crm', 'contact_created',      1.0,  'New contact created'),
    ('crm', 'deal_updated',         1.0,  'Deal record updated'),
    ('crm', 'deal_lost',           -8.0,  'Deal lost')
ON CONFLICT (module, event_type) DO NOTHING;

INSERT INTO schema_migrations (version, note) VALUES
    ('008_reward_config_reconciliation', 'Seed event types emitted by tracker/webhook/sync so the unified reward pipeline resolves them')
ON CONFLICT (version) DO NOTHING;

-- =============================================================================
--  KNOWN REMAINING GAP (deliberate, not an oversight)
--
--  tracking._event_reward emits a DYNAMIC type for partial scrolls:
--      return f"scroll_depth_{pct}", 1.0
--  That is an unbounded set of names (scroll_depth_23, _47, ...) and cannot be
--  enumerated in a config table. Those keep falling back to the caller-supplied
--  default of 1.0, which is why record_event() retains a `default_reward`
--  parameter rather than treating this table as the only source.
--
--  Verify:
--    SELECT module, event_type, reward_value FROM reward_config
--     WHERE module IN ('crm','website') ORDER BY module, event_type;
-- =============================================================================
