"""
Phase 3 — P1 (blocking DB calls) and P3 (per-event insert loop) on /track.
"""

import inspect

from tests.conftest import DEV_USER_ID


def _seed_tracker(supa, token="tok-123"):
    supa.seed("integrations", [{
        "id": "int-1", "user_id": DEV_USER_ID, "module": "website",
        "status": "active", "webhook_secret": token,
    }])
    supa.seed("events", [])
    return token


def test_track_batch_inserts_all_events(client, supa):
    token = _seed_tracker(supa)
    r = client.post("/api/v1/track", json={
        "token": token, "session_id": "s1",
        "events": [{"type": "page_view", "path": "/a"},
                   {"type": "cta_click", "path": "/b"},
                   {"type": "form_submit", "path": "/c"}],
    })
    assert r.status_code == 200
    assert r.json()["accepted"] == 3
    assert len(supa.table("events").select("*").execute().data) == 3


def test_track_uses_a_single_bulk_insert(client, supa):
    """
    P3: one round-trip per batch, not one per event. Counting insert calls is
    the only way to prove the N+1 is gone — the response looks identical.
    """
    token = _seed_tracker(supa)
    calls = {"n": 0}
    original = type(supa).table

    def counting_table(self, name):
        builder = original(self, name)
        if name == "events":
            real_insert = builder.insert
            def wrapped(payload, *a, **k):
                calls["n"] += 1
                return real_insert(payload, *a, **k)
            builder.insert = wrapped
        return builder

    type(supa).table = counting_table
    try:
        client.post("/api/v1/track", json={
            "token": token, "session_id": "s",
            "events": [{"type": "page_view"} for _ in range(20)],
        })
    finally:
        type(supa).table = original

    assert calls["n"] == 1, f"expected 1 bulk insert, got {calls['n']} (N+1 regression)"


def test_track_survives_a_malformed_event(client, supa):
    """
    A null `pct` used to raise TypeError OUTSIDE the try block -> unhandled
    500, discarding every other event in the batch.
    """
    token = _seed_tracker(supa)
    r = client.post("/api/v1/track", json={
        "token": token, "session_id": "s",
        "events": [
            {"type": "page_view", "path": "/ok"},
            {"type": "scroll_depth", "data": {"pct": None}},   # poison
            {"type": "cta_click", "path": "/ok2"},
        ],
    })
    assert r.status_code == 200, "one malformed event killed the whole batch"
    assert r.json()["accepted"] == 2, "good events were dropped"


def test_track_caps_batch_at_50(client, supa):
    token = _seed_tracker(supa)
    r = client.post("/api/v1/track", json={
        "token": token, "session_id": "s",
        "events": [{"type": "page_view"} for _ in range(120)],
    })
    assert r.json()["accepted"] == 50


# ── P1: hot-path DB calls must be off the event loop ──────────────────────

def test_auth_admin_check_is_offloaded():
    """is_admin_user runs on EVERY authenticated request."""
    from app.auth import dependencies
    src = inspect.getsource(dependencies.is_admin_user)
    assert "await q(" in src, "profiles lookup still blocks the event loop"


def test_track_db_calls_are_offloaded():
    from app.api.v1 import tracking
    src = inspect.getsource(tracking.receive_tracking_events)
    assert "await q(" in src, "tracker writes still block the event loop"


def test_q_helper_offloads_to_thread():
    """The helper must actually use to_thread, not just wrap the call."""
    from app import database
    src = inspect.getsource(database.q)
    assert "to_thread" in src


# ── P2: user-discovery scan must be bounded ────────────────────────────────

def test_user_discovery_query_is_bounded():
    """
    An unbounded select over `events` is both a perf problem and a silent
    correctness bug: PostgREST truncates, so users past the cap are never
    scanned while users_scanned still looks plausible.
    """
    import inspect
    from app.core.intelligence import decision_generator as dg

    src = inspect.getsource(dg.run_decision_generator)

    # Strip comment lines before checking. The fix's own comment QUOTES the old
    # unbounded query to explain what changed, so a naive substring search over
    # raw source matches documentation and fails spuriously.
    code = "\n".join(
        ln for ln in src.splitlines() if not ln.lstrip().startswith("#")
    )

    assert 'db.table("events").select("user_id").execute()' not in code, \
        "user discovery is still an unbounded full-table scan"
    assert ".limit(_USER_SCAN_ROW_LIMIT)" in code, "no explicit row cap"
    assert ".gte(" in code, "no recency filter on user discovery"


def test_user_scan_lookback_covers_widest_generator_window():
    """
    The discovery window must be >= the widest trigger lookback, or users with
    activity inside a trigger's window would be excluded from scanning.
    """
    from app.core.intelligence import decision_generator as dg
    assert dg._USER_SCAN_LOOKBACK_DAYS >= 7, \
        "discovery window is narrower than the 7-day CRM no-response trigger"
