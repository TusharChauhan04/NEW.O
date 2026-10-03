"""
Phase 2 regression locks — C2 (dedup) and C3 (OAuth refresh wiring).
"""

import inspect

from tests.conftest import DEV_USER_ID


# ── C2: dedup must match on the stable trigger, not the interpolated action ──

async def test_dedup_matches_on_trigger_not_action(supa):
    """
    A decision inserted with trigger=high_no_response must suppress a second
    one, even though the action text interpolates a changing count.
    """
    from app.core.intelligence.decision_generator import _already_generated

    supa.seed("decisions", [{
        "id": "d1", "user_id": DEV_USER_ID, "module": "crm",
        "action": "Launch follow-up campaign — 3 leads unresponsive",
        "state_snapshot": {"trigger": "high_no_response", "auto_generated": True},
        "created_at": "2099-01-01T00:00:00+00:00",
    }])

    db = supa
    assert await _already_generated(db, DEV_USER_ID, "crm", "high_no_response") is True, \
        "duplicate trigger was not detected — decisions will regenerate hourly"


async def test_dedup_does_not_suppress_a_different_trigger(supa):
    """Guard against over-matching: an unrelated trigger must still fire."""
    from app.core.intelligence.decision_generator import _already_generated

    supa.seed("decisions", [{
        "id": "d1", "user_id": DEV_USER_ID, "module": "crm",
        "state_snapshot": {"trigger": "high_no_response"},
        "created_at": "2099-01-01T00:00:00+00:00",
    }])
    assert await _already_generated(supa, DEV_USER_ID, "crm", "no_activity_5d") is False


async def test_dedup_is_scoped_per_user(supa):
    """Another tenant's decision must not suppress this tenant's."""
    from app.core.intelligence.decision_generator import _already_generated

    supa.seed("decisions", [{
        "id": "d1", "user_id": "other-tenant", "module": "crm",
        "state_snapshot": {"trigger": "no_activity_5d"},
        "created_at": "2099-01-01T00:00:00+00:00",
    }])
    assert await _already_generated(supa, DEV_USER_ID, "crm", "no_activity_5d") is False


def test_no_caller_passes_an_interpolated_action_to_dedup():
    """
    Structural guard: every _already_generated CALL must pass a literal
    trigger string, never `action` or a dedup_key variable.

    NOTE: inspect only the call lines, not the whole module source — the
    function's own docstring explains the dedup_key bug, so a naive substring
    search over the source matches documentation and fails spuriously.
    """
    from app.core.intelligence import decision_generator
    src = inspect.getsource(decision_generator)

    call_lines = [
        ln.strip() for ln in src.splitlines()
        if "_already_generated(db" in ln and "async def" not in ln
    ]
    assert len(call_lines) == 6, f"expected 6 dedup call sites, found {len(call_lines)}"

    for ln in call_lines:
        args = ln.split("_already_generated(", 1)[1]
        assert ", action" not in args, f"call passes the interpolated action: {ln}"
        assert "dedup_key" not in args, f"call still uses dedup_key: {ln}"
        # third positional arg must be a quoted literal trigger
        assert args.count('"') >= 4, f"trigger is not a string literal: {ln}"


# ── C3: CRM sync must use the refresh-aware token accessor ──────────────────

def test_crm_sync_uses_refresh_aware_token():
    """
    run_crm_sync must call get_valid_access_token(), not read the raw stored
    token. Without this, syncs 401 one hour after connect while a valid
    refresh token sits unused.
    """
    from app.core.integrations import crm_sync
    src = inspect.getsource(crm_sync.run_crm_sync)
    assert "get_valid_access_token" in src, "sync still reads the raw stored token"
    assert 'config.get("access_token"' not in src, "sync still bypasses refresh"


def test_get_valid_access_token_is_now_reachable():
    """It had zero call sites before — confirm it is wired in somewhere."""
    import subprocess, sys, pathlib
    root = pathlib.Path(__file__).resolve().parents[1] / "app"
    hits = []
    for f in root.rglob("*.py"):
        text = f.read_text(encoding="utf-8")
        for line in text.splitlines():
            if "get_valid_access_token" in line and "def get_valid_access_token" not in line:
                hits.append(f"{f.name}: {line.strip()[:70]}")
    assert hits, "get_valid_access_token is still dead code"


# ── C4: global_level must act as a ceiling (the platform-wide pause) ────────

def test_global_observe_caps_every_module():
    """The kill switch: global=observe must override permissive module levels."""
    from app.core.intelligence.decision_generator import _resolve_level
    assert _resolve_level("autonomous", "observe") == "observe"
    assert _resolve_level("assist", "observe") == "observe"


def test_global_ceiling_allows_more_restrictive_module():
    """A module may be stricter than the account default."""
    from app.core.intelligence.decision_generator import _resolve_level
    assert _resolve_level("observe", "autonomous") == "observe"
    assert _resolve_level("assist", "autonomous") == "assist"


def test_module_level_used_when_within_ceiling():
    from app.core.intelligence.decision_generator import _resolve_level
    assert _resolve_level("assist", "assist") == "assist"
    assert _resolve_level("autonomous", "autonomous") == "autonomous"


def test_missing_module_level_falls_back_to_global():
    from app.core.intelligence.decision_generator import _resolve_level
    assert _resolve_level(None, "observe") == "observe"
    assert _resolve_level(None, "assist") == "assist"


def test_unknown_level_does_not_escalate():
    """An unexpected value must not be treated as more permissive."""
    from app.core.intelligence.decision_generator import _resolve_level
    assert _resolve_level("bogus", "observe") == "observe"


# ── S4: SSRF via user-writable config.api_domain ───────────────────────────

def test_ssrf_cloud_metadata_endpoint_is_rejected():
    """The classic SSRF target must never become the request base."""
    from app.core.integrations.crm_sync import _safe_zoho_base, DEFAULT_ZOHO_BASE
    assert _safe_zoho_base("http://169.254.169.254/latest") == DEFAULT_ZOHO_BASE


def test_ssrf_rejects_non_https_and_foreign_hosts():
    from app.core.integrations.crm_sync import _safe_zoho_base, DEFAULT_ZOHO_BASE
    for bad in [
        "http://www.zohoapis.com",          # right host, wrong scheme
        "https://evil.com",
        "https://zohoapis.com.evil.com",    # suffix-confusion attempt
        "https://localhost:8000",
        "file:///etc/passwd",
        "https://127.0.0.1",
    ]:
        assert _safe_zoho_base(bad) == DEFAULT_ZOHO_BASE, f"accepted {bad}"


def test_ssrf_allows_legitimate_zoho_data_centres():
    """Guard against over-blocking: real Zoho DCs must still work."""
    from app.core.integrations.crm_sync import _safe_zoho_base
    assert _safe_zoho_base("https://www.zohoapis.eu") == "https://www.zohoapis.eu"
    assert _safe_zoho_base("https://www.zohoapis.in") == "https://www.zohoapis.in"
    assert _safe_zoho_base("https://www.zohoapis.com/") == "https://www.zohoapis.com"


def test_ssrf_strips_path_and_query():
    """Only scheme+host survive, so no path smuggling."""
    from app.core.integrations.crm_sync import _safe_zoho_base
    assert _safe_zoho_base("https://www.zohoapis.com/evil?x=1") == "https://www.zohoapis.com"


def test_ssrf_empty_domain_uses_default():
    from app.core.integrations.crm_sync import _safe_zoho_base, DEFAULT_ZOHO_BASE
    assert _safe_zoho_base("") == DEFAULT_ZOHO_BASE
    assert _safe_zoho_base(None) == DEFAULT_ZOHO_BASE


# ── C5: confidence stored 0-1, displayed as a percentage ───────────────────

def test_mistake_severity_threshold_uses_stored_scale():
    """
    `> 90` on a 0.0-1.0 value is unreachable, so every mistake was labelled
    "medium" forever. The comparison must be against the stored scale.
    """
    import inspect
    from app.api.v1 import analytics
    code = "\n".join(
        ln for ln in inspect.getsource(analytics).splitlines()
        if not ln.lstrip().startswith("#")
    )
    assert '(d.get("confidence") or 0) > 90' not in code, "unreachable severity branch remains"
    assert '(d.get("confidence") or 0) > 0.90' in code, "severity threshold not on the 0-1 scale"


def test_avg_confidence_is_converted_to_percent():
    """The KPI card is labelled '%', so 0.9 must render as 90.0 not 0.9."""
    import inspect
    from app.api.v1 import analytics
    code = "\n".join(
        ln for ln in inspect.getsource(analytics).splitlines()
        if not ln.lstrip().startswith("#")
    )
    assert "* 100" in code, "avg_confidence is still emitted on the 0-1 scale under a % label"


# ── C6: plan vocabulary must be consistent across modules ──────────────────

def test_plan_gate_keys_match_the_accepted_plan_values():
    """
    profile.py validates {starter, growth, enterprise}. PLAN_GATES had 'pro',
    so get_plan_gate('growth') missed and an upgraded customer silently kept
    starter limits.
    """
    from app.api.v1.user_autonomy import PLAN_GATES
    assert set(PLAN_GATES) == {"starter", "growth", "enterprise"}, \
        f"plan vocabulary mismatch: {sorted(PLAN_GATES)}"


def test_growth_plan_actually_grants_autonomous():
    from app.api.v1.user_autonomy import get_plan_gate, level_allowed
    gate = get_plan_gate("growth")
    assert level_allowed("autonomous", "crm", gate) is True, \
        "growth plan still falls back to the starter gate"
    # shield is deliberately excluded from the growth tier
    assert level_allowed("autonomous", "shield", gate) is False


def test_unknown_plan_still_falls_back_to_most_restrictive():
    from app.api.v1.user_autonomy import get_plan_gate, level_allowed
    gate = get_plan_gate("enterprise-trial-typo")
    assert level_allowed("autonomous", "crm", gate) is False
