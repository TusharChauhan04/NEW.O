"""
Integration tests for the security fixes — exercised through the real HTTP
routes, not by calling functions directly.

Each test here corresponds to a specific fix and would FAIL against the
pre-fix code. That's the point: these are regression locks, not coverage
padding. The bug each one guards is named in its docstring.
"""

import hashlib
import hmac

from jose import jwt

from tests.conftest import DEV_USER_ID


# ── BUG-05: unauthenticated IDOR leaking tenant tracking secrets ───────────
# Pre-fix, GET /track/snippet/{id} had no auth dependency and no ownership
# check: anyone who knew an integration_id got that tenant's live tracking
# token back in plaintext.

def test_tracker_snippet_returns_token_for_own_integration(client, supa):
    supa.seed("integrations", [{
        "id": "int-mine", "user_id": DEV_USER_ID, "module": "website",
        "status": "active", "webhook_secret": "secret-abc",
    }])

    r = client.get("/api/v1/track/snippet/int-mine")

    assert r.status_code == 200
    assert r.json()["token"] == "secret-abc"


def test_tracker_snippet_refuses_another_users_integration(client, supa):
    """The ownership filter must exclude integrations the caller doesn't own."""
    supa.seed("integrations", [{
        "id": "int-theirs", "user_id": "a-different-tenant", "module": "website",
        "status": "active", "webhook_secret": "victim-token",
    }])

    r = client.get("/api/v1/track/snippet/int-theirs")

    assert r.status_code == 404
    assert "victim-token" not in r.text


def test_tracker_snippet_requires_authentication(client, supa, monkeypatch):
    """With real auth on, an anonymous caller must not reach the handler."""
    from app.config import settings
    monkeypatch.setattr(settings, "AUTH_REQUIRED", True)
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "test-secret")

    supa.seed("integrations", [{
        "id": "int-x", "user_id": "someone", "module": "website",
        "status": "active", "webhook_secret": "should-not-leak",
    }])

    r = client.get("/api/v1/track/snippet/int-x")

    assert r.status_code == 401
    assert "should-not-leak" not in r.text


# ── BUG-04: inbound webhook HMAC bypassable by omitting the header ─────────
# Pre-fix the guard was `if sig_header and not sig_valid: reject`, so sending
# no signature at all skipped verification entirely.

def _seed_webhook_integration(supa, secret="hook-secret"):
    supa.seed("integrations", [{
        "id": "hook-1", "user_id": DEV_USER_ID, "module": "crm",
        "platform": "custom", "status": "active", "webhook_secret": secret,
    }])
    return secret


def test_inbound_webhook_rejects_missing_signature(client, supa):
    _seed_webhook_integration(supa)

    r = client.post("/api/v1/integrations/inbound/hook-1", content='{"lead":"x"}')

    assert r.status_code == 401


def test_inbound_webhook_rejects_wrong_signature(client, supa):
    _seed_webhook_integration(supa)

    r = client.post(
        "/api/v1/integrations/inbound/hook-1",
        content='{"lead":"x"}',
        headers={"X-NeuralOrbit-Signature": "deadbeef"},
    )

    assert r.status_code == 401


def test_inbound_webhook_accepts_valid_signature(client, supa):
    """
    Guards against over-correcting into blanket rejection: a correctly signed
    payload must still get through.

    NOTE the signature format changed from SHA256(secret ‖ body) to
    HMAC-SHA256(secret, body) — the old construction was length-extendable.
    Any external webhook sender must be updated to match.
    """
    secret = _seed_webhook_integration(supa)
    body = '{"lead":"x"}'
    signature = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()

    r = client.post(
        "/api/v1/integrations/inbound/hook-1",
        content=body,
        headers={"X-NeuralOrbit-Signature": signature},
    )

    assert r.status_code != 401


# ── BUG-06: admin check read the wrong JWT claim ───────────────────────────
# A real Supabase JWT always carries role="authenticated"; the app role lives
# in the profiles table. Pre-fix code compared the top-level claim to "admin",
# which is never true for a genuine token — silently breaking cross-tenant
# admin views for real logins while appearing to work under the dev bypass.

def _real_jwt(sub, secret="test-secret"):
    return jwt.encode(
        {"sub": sub, "aud": "authenticated", "role": "authenticated"},
        secret,
        algorithm="HS256",
    )


def _seed_two_tenants_decisions(supa):
    supa.seed("decisions", [
        {"id": "d1", "user_id": "tenant-a", "module": "crm", "outcome": "pending"},
        {"id": "d2", "user_id": "tenant-b", "module": "crm", "outcome": "pending"},
    ])


def test_non_admin_cannot_see_other_tenants_decisions(client, supa, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "AUTH_REQUIRED", True)
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "test-secret")

    _seed_two_tenants_decisions(supa)
    supa.seed("profiles", [{"id": "tenant-a", "role": "user"}])

    r = client.get(
        "/api/v1/decisions?all=true",
        headers={"Authorization": f"Bearer {_real_jwt('tenant-a')}"},
    )

    assert r.status_code == 200
    returned = r.json()["decisions"]
    assert [d["id"] for d in returned] == ["d1"], "non-admin leaked another tenant's rows"


def test_real_admin_jwt_sees_all_tenants_decisions(client, supa, monkeypatch):
    """
    The regression that matters: with a genuine Supabase token (role claim =
    "authenticated"), an admin must still be recognised as admin via the
    profiles table.
    """
    from app.config import settings
    monkeypatch.setattr(settings, "AUTH_REQUIRED", True)
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "test-secret")

    _seed_two_tenants_decisions(supa)
    supa.seed("profiles", [{"id": "tenant-a", "role": "admin"}])

    r = client.get(
        "/api/v1/decisions?all=true",
        headers={"Authorization": f"Bearer {_real_jwt('tenant-a')}"},
    )

    assert r.status_code == 200
    returned_ids = sorted(d["id"] for d in r.json()["decisions"])
    assert returned_ids == ["d1", "d2"], "admin did not receive cross-tenant rows"


# ── BUG-13: module whitelist not enforced on decision/integration create ───

def test_event_rejects_unknown_module(client, supa):
    r = client.post(
        "/api/v1/events",
        json={"module": "not-a-real-module", "event_type": "x"},
    )
    assert r.status_code == 400


def test_event_accepts_valid_module(client, supa):
    r = client.post(
        "/api/v1/events",
        json={"module": "crm", "event_type": "lead_reply"},
    )
    assert r.status_code == 201


def test_decision_rejects_unknown_module(client, supa):
    r = client.post(
        "/api/v1/decisions",
        json={"module": "bogus", "action": "do something"},
    )
    assert r.status_code == 400


def test_integration_rejects_unknown_module(client, supa):
    r = client.post(
        "/api/v1/integrations",
        json={"module": "bogus", "platform": "custom", "type": "webhook"},
    )
    assert r.status_code == 400


# ── BUG-14: no rate limiting anywhere ─────────────────────────────────────
# /recommend can trigger a billed LLM call per request.

def test_recommend_is_rate_limited(client, supa):
    payload = {"module": "crm", "question": "what next?"}

    statuses = [
        client.post("/api/v1/recommend", json=payload).status_code
        for _ in range(11)
    ]

    assert 429 in statuses, f"expected a 429 within 11 calls, got {statuses}"
    assert statuses[0] != 429, "first call should not be rate limited"


def test_rate_limit_is_per_user_not_global(client, supa, monkeypatch):
    """
    Two different tenants must not share a bucket — otherwise one busy tenant
    would lock everyone else out.
    """
    from app.core import rate_limit

    for _ in range(10):
        rate_limit.check_rate_limit("recommend:tenant-a", 10, 60)

    # tenant-b's first call must still be allowed
    rate_limit.check_rate_limit("recommend:tenant-b", 10, 60)


# ── Privilege-escalation write paths (the read path was hardened separately) ──
# is_admin_user() correctly trusts only profiles.role. These guard the paths
# that WRITE that column — hardening the reader is useless if any user can
# write the value it reads.

def test_profile_autocreate_never_grants_admin_from_jwt_claims(client, supa, monkeypatch):
    """
    GET /profile auto-creates a missing row. It must hardcode role='user'.
    Reading user_metadata.role here let a user self-promote, because this
    write uses the service-role key and bypasses RLS.
    """
    from app.auth import dependencies
    attacker = {
        "sub": "attacker-uid",
        "email": "a@b.c",
        "role": "authenticated",
        "user_metadata": {"role": "admin", "name": "A"},
        "app_metadata": {"role": "admin"},
    }
    monkeypatch.setattr(dependencies, "_DEV_USER", attacker)

    supa.seed("profiles", [])
    r = client.get("/api/v1/profile")

    assert r.status_code == 200
    assert r.json()["profile"]["role"] == "user", "auto-created profile granted admin from JWT claims"
    stored = supa.table("profiles").select("*").execute().data
    assert all(p["role"] == "user" for p in stored), "admin role was persisted to the DB"
