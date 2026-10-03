-- ============================================================
--  NeuralOrbit — User Profiles Table
--  Run this ONCE in: Supabase Dashboard → SQL Editor
--
--  SAFE: This script is purely ADDITIVE.
--  It creates new things (table, trigger, policy).
--  It does NOT modify, alter, or drop any existing table.
-- ============================================================

-- ── 1. Create the profiles table ─────────────────────────────
CREATE TABLE IF NOT EXISTS public.profiles (
    id          UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name   TEXT,
    company     TEXT,
    plan        TEXT NOT NULL DEFAULT 'starter',   -- starter | growth | enterprise
    role        TEXT NOT NULL DEFAULT 'user',       -- user | admin
    avatar_url  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── 2. Index for fast lookups ─────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_profiles_role ON public.profiles(role);

-- ── 3. Row Level Security ─────────────────────────────────────
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- Drop old policies first (safe to re-run)
DROP POLICY IF EXISTS "own_profile_read"   ON public.profiles;
DROP POLICY IF EXISTS "own_profile_write"  ON public.profiles;
DROP POLICY IF EXISTS "admin_read_all"     ON public.profiles;
DROP POLICY IF EXISTS "service_role_all"   ON public.profiles;

-- Users can read & update ONLY their own profile
CREATE POLICY "own_profile_read"  ON public.profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "own_profile_write" ON public.profiles
    FOR UPDATE USING (auth.uid() = id);

-- Service role (backend) can read ALL profiles (for admin APIs)
CREATE POLICY "service_role_all"  ON public.profiles
    FOR ALL USING (auth.role() = 'service_role');

-- ── 4. Auto-create profile on every new sign-up ───────────────
-- This trigger fires automatically when someone registers.
-- It reads name/role from the user_metadata they passed at signup.

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
        COALESCE(NEW.raw_user_meta_data->>'role', 'user')
    )
    ON CONFLICT (id) DO NOTHING;  -- idempotent: safe to re-run
    RETURN NEW;
END;
$$;

-- Bind trigger to auth.users
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user();

-- ── 5. Backfill: create profile rows for existing users ───────
-- Safe for re-runs (ON CONFLICT DO NOTHING)
INSERT INTO public.profiles (id, full_name, company, role, created_at)
SELECT
    id,
    COALESCE(raw_user_meta_data->>'name', email) AS full_name,
    raw_user_meta_data->>'company'               AS company,
    COALESCE(raw_user_meta_data->>'role', 'user') AS role,
    created_at
FROM auth.users
ON CONFLICT (id) DO NOTHING;

-- ── Done ──────────────────────────────────────────────────────
-- After running this:
--   1. Every new sign-up will auto-create a profile row
--   2. All existing users now have a profile row
--   3. Admin backend can query profiles via service_role key
-- ============================================================
