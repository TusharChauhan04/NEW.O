-- ============================================================
-- bootstrap_admin.sql
-- NeuralOrbit — Admin Account Bootstrap (Full Fix)
--
-- INSTRUCTIONS:
--   1. Open Supabase Dashboard → SQL Editor
--   2. Run Step 0 first (diagnostic) to see current state
--   3. Run Step 1 to create/update the profiles row
--   4. Run Step 2 to verify
--
-- WHY THE PREVIOUS UPDATE MIGHT HAVE FAILED:
--   The profiles table has RLS (Row Level Security) enabled.
--   Even in the SQL Editor you may need to SET LOCAL role = 'postgres'
--   to bypass RLS. This script does that automatically.
-- ============================================================

-- ── Step 0: Diagnostic — run this first to see current state ─────
-- SELECT id, full_name, role, plan FROM profiles
-- WHERE id = 'c9d5156b-e6d6-4afd-bc3b-fb2a8e5f104a';
--
-- If NO ROWS returned: your profile row doesn't exist yet → Step 1A
-- If role = 'user': row exists but needs update → Step 1B
-- If role = 'admin': already done ✅

-- ── Step 1: Bypass RLS and upsert admin profile ──────────────────
-- This handles BOTH cases: row doesn't exist AND row exists as user.

-- Temporarily disable RLS for this transaction (postgres superuser)
ALTER TABLE public.profiles DISABLE ROW LEVEL SECURITY;

-- Upsert: create if missing, update role to admin if exists
INSERT INTO public.profiles (id, full_name, role, plan, created_at, updated_at)
VALUES (
    'c9d5156b-e6d6-4afd-bc3b-fb2a8e5f104a',
    'Tushar (Admin)',
    'admin',
    'enterprise',
    NOW(),
    NOW()
)
ON CONFLICT (id) DO UPDATE
    SET role       = 'admin',
        plan       = 'enterprise',
        updated_at = NOW();

-- Re-enable RLS
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- ── Step 2: Verify ───────────────────────────────────────────────
SELECT id, full_name, role, plan, updated_at
FROM profiles
WHERE id = 'c9d5156b-e6d6-4afd-bc3b-fb2a8e5f104a';

-- ── Step 3: Also update auth.users user_metadata (for JWT claims) ─
-- This ensures the JWT token itself carries role=admin after next login.
UPDATE auth.users
SET raw_user_meta_data = raw_user_meta_data || '{"role": "admin"}'::jsonb,
    raw_app_meta_data  = raw_app_meta_data  || '{"role": "admin"}'::jsonb
WHERE id = 'c9d5156b-e6d6-4afd-bc3b-fb2a8e5f104a';

-- ── Step 4: Final verify ──────────────────────────────────────────
SELECT
    u.id,
    u.email,
    u.raw_user_meta_data->>'role'  AS jwt_role,
    u.raw_app_meta_data->>'role'   AS app_role,
    p.role                         AS profile_role,
    p.plan                         AS profile_plan
FROM auth.users u
LEFT JOIN public.profiles p ON p.id = u.id
WHERE u.id = 'c9d5156b-e6d6-4afd-bc3b-fb2a8e5f104a';

-- ── WHAT TO EXPECT IN RESULTS ─────────────────────────────────────
-- jwt_role    = admin  ← makes JWT carry admin role
-- app_role    = admin  ← used by Supabase auth.users policies
-- profile_role = admin ← used by NeuralOrbit backend (source of truth)
-- profile_plan = enterprise ← gives full autonomy access
-- ============================================================
-- AFTER RUNNING THIS:
--   1. Log OUT of NeuralOrbit completely (clear localStorage)
--   2. Log back IN with your real email/password
--   3. You will be redirected to admin/neural-orbit.html
-- ============================================================
