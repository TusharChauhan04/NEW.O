"""
Phase 5 (C1) — every ingest path must run the shared reward pipeline.

Before this, only POST /events did. /track, the inbound webhook, and the Zoho
sync wrote to `events` and stopped, so module_states.cumulative_reward — the
number fed to the LLM as "how much value has this customer produced" — stayed
at 0 for any customer whose data arrived by tracker, webhook, or CRM sync.
"""

import pathlib

from tests.conftest import DEV_USER_ID


def _cum(supa, module="website", user_id=DEV_USER_ID):
    for r in supa.table("module_states").select("*").execute().data:
        if r.get("user_id") == user_id and r.get("module") == module:
            return r.get("cumulative_reward")
    return None


# ── record_event: the shared pipeline ──────────────────────────────────────

async def test_record_event_writes_event_reward_and_cumulative(supa):
    from app.core.intelligence.reward_engine import record_event
    supa.seed("reward_config", [
        {"module": "crm", "event_type": "deal_closed", "reward_value": 21.0, "is_active": True},
    ])

    out = await record_event(
        user_id=DEV_USER_ID, module="crm", event_type="deal_closed",
        payload={"x": 1}, source="zoho",
    )

    assert out.get("reward_value") == 21.0
    assert len(supa.table("events").select("*").execute().data) == 1
    assert len(supa.table("rewards").select("*").execute().data) == 1, "no rewards row written"
    assert _cum(supa, "crm") == 21.0, "module_states.cumulative_reward not updated"


async def test_reward_config_takes_priority_over_caller_default(supa):
    """The DB table is authoritative so admins can retune without a redeploy."""
    from app.core.intelligence.reward_engine import record_event
    supa.seed("reward_config", [
        {"module": "crm", "event_type": "deal_closed", "reward_value": 99.0, "is_active": True},
    ])
    out = await record_event(
        user_id=DEV_USER_ID, module="crm", event_type="deal_closed",
        default_reward=21.0,
    )
    assert out["reward_value"] == 99.0, "hardcoded map beat the config table"


async def test_caller_default_used_when_config_has_no_row(supa):
    """
    THE reason the hardcoded maps were kept as a fallback rather than deleted.
    ~19 emitted event types had no config row; without this they would all
    silently resolve to no reward.
    """
    from app.core.intelligence.reward_engine import record_event
    supa.seed("reward_config", [
        {"module": "crm", "event_type": "something_else", "reward_value": 1.0, "is_active": True},
    ])
    out = await record_event(
        user_id=DEV_USER_ID, module="website", event_type="scroll_depth_42",
        default_reward=1.0,
    )
    assert out["reward_value"] == 1.0, "unseeded event type lost its reward"
    assert _cum(supa, "website") == 1.0


async def test_no_reward_when_neither_config_nor_default(supa):
    from app.core.intelligence.reward_engine import record_event
    supa.seed("reward_config", [
        {"module": "crm", "event_type": "x", "reward_value": 1.0, "is_active": True},
    ])
    out = await record_event(
        user_id=DEV_USER_ID, module="website", event_type="totally_unknown",
    )
    assert out["reward_value"] is None
    assert supa.table("rewards").select("*").execute().data == []


# ── bulk sibling ───────────────────────────────────────────────────────────

async def test_bulk_aggregates_into_one_cumulative_update(supa):
    from app.core.intelligence.reward_engine import record_events_bulk
    supa.seed("reward_config", [
        {"module": "website", "event_type": "page_view", "reward_value": 1.0, "is_active": True},
    ])
    n = await record_events_bulk(
        user_id=DEV_USER_ID, module="website", source="tracker",
        items=[{"event_type": "page_view", "payload": {}, "default_reward": 1.0} for _ in range(5)],
    )
    assert n == 5
    assert _cum(supa) == 5.0, "rewards were not summed into cumulative_reward"


async def test_bulk_still_uses_a_single_events_insert(supa):
    """Phase 3's N+1 fix must survive the Phase 5 refactor."""
    from app.core.intelligence.reward_engine import record_events_bulk
    calls = {"n": 0}
    original = type(supa).table

    def counting_table(self, name):
        b = original(self, name)
        if name == "events":
            real = b.insert

            def wrapped(p, *a, **k):
                calls["n"] += 1
                return real(p, *a, **k)
            b.insert = wrapped
        return b

    type(supa).table = counting_table
    try:
        await record_events_bulk(
            user_id=DEV_USER_ID, module="website", source="tracker",
            items=[{"event_type": "page_view", "default_reward": 1.0} for _ in range(20)],
        )
    finally:
        type(supa).table = original
    assert calls["n"] == 1, f"expected 1 bulk insert, got {calls['n']}"


# ── the actual C1 symptom, end to end ──────────────────────────────────────

def test_track_endpoint_now_updates_cumulative_reward(client, supa):
    """
    A customer with the tracker installed used to show cumulative_reward = 0
    no matter how much traffic they had.
    """
    supa.seed("integrations", [{
        "id": "int-1", "user_id": DEV_USER_ID, "module": "website",
        "status": "active", "webhook_secret": "tok-1",
    }])
    supa.seed("reward_config", [
        {"module": "website", "event_type": "page_view", "reward_value": 1.0, "is_active": True},
    ])

    r = client.post("/api/v1/track", json={
        "token": "tok-1", "session_id": "s",
        "events": [{"type": "page_view"}, {"type": "page_view"}, {"type": "page_view"}],
    })
    assert r.status_code == 200
    assert _cum(supa) == 3.0, "tracker traffic still does not reach module_states"
    assert len(supa.table("rewards").select("*").execute().data) == 3


# ── structural: one pipeline, four callers ─────────────────────────────────

def test_every_ingest_path_uses_the_shared_pipeline():
    """No writer may insert into `events` directly any more."""
    app_dir = pathlib.Path(__file__).resolve().parents[1] / "app"
    needle = 'table("events").insert'
    offenders = []
    for f in app_dir.rglob("*.py"):
        if f.name == "reward_engine.py":
            continue   # the one legitimate writer
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if needle in line:
                offenders.append(f"{f.relative_to(app_dir)}:{i}")
    assert not offenders, f"ingest paths bypassing the reward pipeline: {offenders}"


def test_all_four_writers_call_record_event():
    app_dir = pathlib.Path(__file__).resolve().parents[1] / "app"
    expected = {
        "api/v1/events.py":              "record_event",
        "api/v1/tracking.py":            "record_events_bulk",
        "api/v1/integrations.py":        "record_event",
        "core/integrations/crm_sync.py": "record_event",
    }
    for rel, fn in expected.items():
        text = (app_dir / rel).read_text(encoding="utf-8")
        code = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
        assert fn in code, f"{rel} does not call {fn}"


# ── migration reconciles the names the writers actually emit ───────────────

def test_migration_seeds_the_names_the_tracker_emits():
    """
    reward_config was seeded with 'engaged_session'/'bounce' while the tracker
    emits 'session_engaged'/'session_bounce' (reversed word order).
    """
    sql = (pathlib.Path(__file__).resolve().parents[1]
           / "migrations" / "008_reward_config_reconciliation.sql").read_text(encoding="utf-8")
    for name in ["session_engaged", "session_bounce", "cta_click",
                 "scroll_depth_full", "scroll_depth_high", "checkout_complete"]:
        assert f"'{name}'" in sql, f"migration does not seed {name}"


def test_migration_is_non_destructive():
    sql = (pathlib.Path(__file__).resolve().parents[1]
           / "migrations" / "008_reward_config_reconciliation.sql").read_text(encoding="utf-8")
    code = "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("--"))
    for verb in ["DROP", "DELETE FROM", "TRUNCATE", "UPDATE "]:
        assert verb not in code.upper(), f"migration contains {verb}"
    assert code.upper().count("ON CONFLICT") == 2, "inserts are not all idempotent"
