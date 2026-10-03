-- ============================================================
-- Phase 4 — Test Data Seed
-- This script populates the database with realistic events and decisions
-- so you can test the Learning Engine and Decision Log immediately.
-- ============================================================

-- 1. Insert some initial Website and CRM events
-- Replace 'YOUR_USER_ID' if you want these specifically for your account, 
-- but the backend will pick up the first user it finds.
-- We use a subquery to get the first user_id from the users/auth table if possible.

DO $$
DECLARE
    target_user_id UUID;
BEGIN
    SELECT id INTO target_user_id FROM auth.users LIMIT 1;
    
    IF target_user_id IS NULL THEN
        RAISE NOTICE 'No user found in auth.users. Please sign up in the app first.';
        RETURN;
    END IF;

    -- Clear old test data if needed (Optional)
    -- DELETE FROM events WHERE payload->>'test' = 'true';
    -- DELETE FROM decisions WHERE state_snapshot->>'auto_generated' = 'true';

    -- 2. Insert CRM Events
    INSERT INTO events (user_id, module, event_type, payload, source) VALUES
    (target_user_id, 'crm', 'lead_created', '{"email": "alex@example.com", "score": 45, "test": true}', 'zoho'),
    (target_user_id, 'crm', 'no_response_7d', '{"email": "alex@example.com", "days_silent": 7, "test": true}', 'system'),
    (target_user_id, 'crm', 'no_response_7d', '{"email": "beth@example.com", "days_silent": 7, "test": true}', 'system'),
    (target_user_id, 'crm', 'no_response_7d', '{"email": "casey@example.com", "days_silent": 8, "test": true}', 'system');

    -- 3. Insert Website Events (High Bounce Scenario)
    INSERT INTO events (user_id, module, event_type, payload, source) VALUES
    (target_user_id, 'website', 'session_bounce', '{"path": "/", "duration": 2, "test": true}', 'tracker'),
    (target_user_id, 'website', 'session_bounce', '{"path": "/pricing", "duration": 5, "test": true}', 'tracker'),
    (target_user_id, 'website', 'session_engaged', '{"path": "/docs", "duration": 120, "test": true}', 'tracker'),
    (target_user_id, 'website', 'session_bounce', '{"path": "/", "duration": 1, "test": true}', 'tracker');

    -- 4. Insert Shield Events (Threat Scenario)
    INSERT INTO events (user_id, module, event_type, payload, source) VALUES
    (target_user_id, 'shield', 'threat_blocked', '{"type": "sql_injection", "ip": "1.2.3.4", "test": true}', 'shield_proxy'),
    (target_user_id, 'shield', 'threat_blocked', '{"type": "brute_force", "ip": "1.2.3.4", "test": true}', 'shield_proxy'),
    (target_user_id, 'shield', 'threat_blocked', '{"type": "xss_attempt", "ip": "1.2.3.4", "test": true}', 'shield_proxy');

    -- 5. Insert some PENDING Decisions (for you to Approve/Reject in the Decision Log)
    INSERT INTO decisions (user_id, module, action, reasoning, confidence, outcome, state_snapshot, alternatives) VALUES
    (target_user_id, 'crm', 'Launch re-engagement for 3 unresponsive leads', 'Three leads have passed the 7-day silence threshold. High probability of churn if no contact in next 24h.', 0.88, 'pending', '{"leads": 3, "auto_generated": true}', '[]'),
    (target_user_id, 'website', 'Optimize Hero Section Headline', 'Bounce rate on home page is currently 65% (Threshold: 40%). Headline lacks clear value prop.', 0.76, 'pending', '{"bounce_rate": 65, "auto_generated": true}', '[]'),
    (target_user_id, 'shield', 'Escalate IP 1.2.3.4 to Global Blocklist', 'Three distinct threat types detected from same IP within 1 hour. Suggests a targeted probe.', 0.94, 'pending', '{"threats": 3, "auto_generated": true}', '[]');

    RAISE NOTICE 'Seed data injected successfully for user %', target_user_id;
END $$;
