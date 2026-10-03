"""
Tests for app/auth/dependencies.py — covers:
  - The AUTH_REQUIRED=false dev-bypass path.
  - Real JWT verification (success + failure) when AUTH_REQUIRED=true.
  - is_admin_user()'s JWT-claim fallback (BUG-06's fix): decisions.py,
    rewards.py, states.py, and analytics.py now all call this instead of
    checking current_user["role"] directly, which is always "authenticated"
    on a real Supabase token and would never equal "admin".
"""

import pytest
from jose import jwt

from app.auth import dependencies
from app.config import settings


async def test_dev_bypass_returns_dev_user_when_auth_not_required(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_REQUIRED", False)
    user = await dependencies.get_current_user(credentials=None)
    assert user["sub"] == dependencies._DEV_USER["sub"]


async def test_get_current_user_rejects_missing_token_when_required(monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setattr(settings, "AUTH_REQUIRED", True)
    with pytest.raises(HTTPException) as exc_info:
        await dependencies.get_current_user(credentials=None)
    assert exc_info.value.status_code == 401


async def test_get_current_user_accepts_valid_jwt(monkeypatch):
    from fastapi.security import HTTPAuthorizationCredentials

    monkeypatch.setattr(settings, "AUTH_REQUIRED", True)
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "test-secret")

    token = jwt.encode(
        {"sub": "11111111-1111-1111-1111-111111111111", "aud": "authenticated", "role": "authenticated"},
        "test-secret",
        algorithm="HS256",
    )
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    user = await dependencies.get_current_user(credentials=creds)
    assert user["sub"] == "11111111-1111-1111-1111-111111111111"


async def test_get_current_user_rejects_wrong_signature(monkeypatch):
    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials

    monkeypatch.setattr(settings, "AUTH_REQUIRED", True)
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "real-secret")

    token = jwt.encode(
        {"sub": "1", "aud": "authenticated"}, "wrong-secret", algorithm="HS256"
    )
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc_info:
        await dependencies.get_current_user(credentials=creds)
    assert exc_info.value.status_code == 401


async def test_is_admin_user_true_via_app_metadata_fallback(monkeypatch):
    # AUTH_REQUIRED=False so is_admin_user skips the DB lookup entirely
    # and falls back to JWT-claim checking — this is the exact path that
    # decisions.py / rewards.py / states.py / analytics.py now use instead
    # of the old `current_user.get("role") == "admin"` bug.
    monkeypatch.setattr(settings, "AUTH_REQUIRED", False)
    current_user = {"sub": "x", "role": "authenticated", "app_metadata": {"role": "admin"}}
    assert await dependencies.is_admin_user(current_user) is True


async def test_is_admin_user_false_for_plain_authenticated_role(monkeypatch):
    # This is the exact bug being regression-tested: a real Supabase JWT's
    # top-level "role" claim is always "authenticated", never the app role.
    monkeypatch.setattr(settings, "AUTH_REQUIRED", False)
    current_user = {"sub": "x", "role": "authenticated"}
    assert await dependencies.is_admin_user(current_user) is False


async def test_get_admin_user_raises_403_for_non_admin(monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setattr(settings, "AUTH_REQUIRED", False)
    current_user = {"sub": "x", "role": "authenticated"}
    with pytest.raises(HTTPException) as exc_info:
        await dependencies.get_admin_user(current_user=current_user)
    assert exc_info.value.status_code == 403


# ── Fail-closed admin checks (privilege-escalation regression guards) ──────
# `user_metadata` is writable by the user via supabase.auth.updateUser().
# It must never grant admin. Before this fix, a DB outage fell back to JWT
# claims including user_metadata, turning any outage into an escalation window.

async def test_user_metadata_role_never_grants_admin_in_dev(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_REQUIRED", False)
    attacker = {"sub": "x", "role": "authenticated", "user_metadata": {"role": "admin"}}
    assert await dependencies.is_admin_user(attacker) is False


async def test_admin_denied_when_profiles_lookup_fails(monkeypatch):
    """DB unreachable while auth is enforced -> deny admin, never fall back."""
    monkeypatch.setattr(settings, "AUTH_REQUIRED", True)

    import app.database
    def _boom():
        raise RuntimeError("supabase unreachable")
    monkeypatch.setattr(app.database, "get_supabase", _boom)

    # Even with admin-looking claims, the outage must not grant admin.
    user = {"sub": "x", "app_metadata": {"role": "admin"}, "user_metadata": {"role": "admin"}}
    assert await dependencies.is_admin_user(user) is False


async def test_admin_denied_when_no_profiles_row(monkeypatch):
    """A user with no profiles row is not an admin."""
    monkeypatch.setattr(settings, "AUTH_REQUIRED", True)

    class _Empty:
        data = []
    class _Q:
        def select(self, *a, **k): return self
        def eq(self, *a, **k): return self
        def limit(self, *a, **k): return self
        def execute(self): return _Empty()
    class _DB:
        def table(self, *a, **k): return _Q()

    import app.database
    monkeypatch.setattr(app.database, "get_supabase", lambda: _DB())

    user = {"sub": "x", "app_metadata": {"role": "admin"}}
    assert await dependencies.is_admin_user(user) is False
