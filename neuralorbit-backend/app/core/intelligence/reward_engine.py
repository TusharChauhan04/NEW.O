"""
core/intelligence/reward_engine.py — NeuralOrbit Reward Engine

Calculates reward values for business events based on:
- Module-specific reward config (loaded from Supabase reward_config table)
- Falls back to hardcoded defaults from your Reward Frameworks document

Phase 1: Rule-based rewards (lookup table)
Phase 2: Will add bandit-adjusted dynamic weights
"""

from datetime import datetime, timezone
from app.database import get_supabase
# q() runs a blocking supabase-py call off the event loop (see database.q).
from app.database import q
_to_thread = q  # historical alias used by record_event/record_events_bulk
import logging

logger = logging.getLogger(__name__)

# ── Default Reward Config ──────────────────────────────────────────────────
# Directly from your "Reward Frameworks (CORE IP)" document
DEFAULT_REWARD_CONFIG: dict[str, dict[str, float]] = {
    "crm": {
        "lead_reply":      3.0,   # Lead replied to outreach
        "meeting_booked":  8.0,   # Meeting successfully booked
        "deal_closed":    21.0,   # Deal closed and won
        "no_response_7d": -4.0,   # No response after 7 days
        "lead_churn":    -10.0,   # Lead churned / lost
    },
    "marketing": {
        "ctr_increase":   5.0,   # Click-through rate increased
        "cpa_decrease":   8.0,   # Cost per acquisition decreased
        "conversion":    15.0,   # Campaign conversion recorded
        "ad_fatigue":    -6.0,   # Ad fatigue detected
        "budget_waste": -10.0,   # Budget waste detected
    },
    "shield": {
        "threat_blocked":        10.0,  # Security threat blocked
        "false_positive":        -3.0,  # False positive alert
        "data_misuse_detected":  15.0,  # Data misuse—flagged
        "breach":               -60.0,  # Security breach occurred
    },
    "website": {
        "page_conversion":       10.0,  # Visitor converted
        "bounce":                -3.0,  # Visitor bounced
        "session_value_high":     8.0,  # High-value session
        "core_vitals_improved":   5.0,  # Performance improved
    },
    "neural-orbit": {
        "decision_applied":   5.0,  # AI decision applied
        "decision_rejected": -2.0,  # AI decision rejected
        "insight_acted_on":   8.0,  # AI insight acted upon
    },
}


async def get_reward_config() -> dict[str, dict[str, float]]:
    """Load reward config from Supabase; fall back to defaults on failure."""
    try:
        db = get_supabase()
        result = (
            await q(db.table("reward_config")
            .select("module, event_type, reward_value")
            .eq("is_active", True))
        )
        if result.data:
            config: dict[str, dict[str, float]] = {}
            for row in result.data:
                m = row["module"]
                if m not in config:
                    config[m] = {}
                config[m][row["event_type"]] = float(row["reward_value"])
            logger.info(f"[RewardEngine] Loaded {len(result.data)} reward rules from DB")
            return config
    except Exception as e:
        logger.warning(f"[RewardEngine] DB config unavailable, using defaults: {e}")

    return DEFAULT_REWARD_CONFIG


async def calculate_reward(module: str, event_type: str) -> float | None:
    """Return reward score for a (module, event_type) pair. None if unknown."""
    config = await get_reward_config()
    return config.get(module, {}).get(event_type)


async def store_reward(
    event_id: str,
    user_id: str,
    module: str,
    event_type: str,
    reward_value: float,
    source: str = "rule_engine",
) -> dict | None:
    """Persist a reward record to the rewards table."""
    try:
        db = get_supabase()
        result = await q(db.table("rewards").insert({
            "event_id": event_id,
            "user_id": user_id,
            "module": module,
            "event_type": event_type,
            "reward_value": reward_value,
            "reward_source": source,
        }))
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"[RewardEngine] Failed to store reward: {e}")
        return None


async def update_module_cumulative_reward(
    user_id: str,
    module: str,
    reward_delta: float,
) -> None:
    """
    Upsert module_states — adds reward_delta to the running total.
    Creates the record if this is the user's first event in this module.
    """
    try:
        db = get_supabase()
        existing = (
            await q(db.table("module_states")
            .select("id, cumulative_reward, decision_count")
            .eq("user_id", user_id)
            .eq("module", module))
        )

        if existing.data:
            row = existing.data[0]
            await q(db.table("module_states").update({
                "cumulative_reward": round(row["cumulative_reward"] + reward_delta, 4),
                "decision_count":    row["decision_count"] + 1,
                "last_updated":      datetime.now(timezone.utc).isoformat(),
            }).eq("id", row["id"]))
        else:
            await q(db.table("module_states").insert({
                "user_id":           user_id,
                "module":            module,
                "state":             {},
                "cumulative_reward": round(reward_delta, 4),
                "decision_count":    1,
            }))

        logger.info(
            f"[RewardEngine] module_states updated — "
            f"user={user_id[:8]} module={module} delta={reward_delta:+.1f}"
        )
    except Exception as e:
        logger.error(f"[RewardEngine] Failed to update module_states: {e}")


# ── Unified ingest path ────────────────────────────────────────────────────────

async def record_event(
    user_id: str,
    module: str,
    event_type: str,
    payload: dict | None = None,
    source: str = "api",
    context: dict | None = None,
    default_reward: float | None = None,
) -> dict:
    """
    Write ONE event and run the full reward pipeline for it.

    This is the single entry point every ingest path must use. Previously only
    POST /events ran the pipeline; /track, the inbound webhook, and the Zoho
    sync each wrote straight to `events` and stopped. The result was that
    module_states.cumulative_reward — the number the whole "AI state" concept
    rests on, and which is fed to the LLM as context — reflected only manually
    POSTed events. A customer with a live Zoho integration and the tracker
    installed showed cumulative_reward = 0, and the LLM then reasoned about a
    customer it believed had produced no value at all.

    REWARD RESOLUTION ORDER
      1. The `reward_config` table (authoritative, admin-tunable at runtime).
      2. `default_reward` supplied by the caller, if config has no matching row.

    Step 2 matters. calculate_reward() returns None for an unknown pair, so
    routing the callers through this helper WITHOUT a fallback would silently
    drop every reward whose event_type is not yet seeded — trading one silent
    failure for another. The callers' existing maps are passed in as the
    fallback so behaviour degrades to what it is today rather than to zero.

    Returns the inserted event row, with "reward_value" attached (None when no
    reward could be resolved).
    """
    db = get_supabase()

    try:
        result = await _to_thread(
            db.table("events").insert({
                "user_id":    user_id,
                "module":     module,
                "event_type": event_type,
                "payload":    payload or {},
                "context":    context or {},
                "source":     source,
            })
        )
    except Exception as e:
        logger.error(f"[RewardEngine] Failed to insert event {module}/{event_type}: {e}")
        raise

    event_data = result.data[0] if result.data else {}
    event_id = event_data.get("id")

    reward_value = await calculate_reward(module, event_type)
    if reward_value is None:
        reward_value = default_reward

    if reward_value is not None and event_id:
        await store_reward(event_id, user_id, module, event_type, reward_value)
        await update_module_cumulative_reward(user_id, module, reward_value)
        event_data["reward_value"] = reward_value
    else:
        event_data["reward_value"] = None

    return event_data


async def record_events_bulk(
    user_id: str,
    module: str,
    items: list[dict],
    source: str = "api",
) -> int:
    """
    Bulk sibling of record_event for high-volume writers (the tracker).

    Inserts every event in ONE round-trip — the /track endpoint handles up to 50
    events per batch and must not regress to one request per event — then
    applies the reward pipeline. The cumulative total is aggregated into a
    SINGLE module_states update rather than one per event.

    `items` entries: {"event_type": str, "payload": dict, "default_reward": float|None}

    Returns the number of events written.
    """
    if not items:
        return 0

    db = get_supabase()

    rows = [{
        "user_id":    user_id,
        "module":     module,
        "event_type": it["event_type"],
        "payload":    it.get("payload") or {},
        "context":    it.get("context") or {},
        "source":     source,
    } for it in items]

    result = await _to_thread(db.table("events").insert(rows))
    inserted = result.data or []

    # Resolve rewards, then fold them into one cumulative update.
    total_delta = 0.0
    reward_rows = []
    for it, row in zip(items, inserted):
        rv = await calculate_reward(module, it["event_type"])
        if rv is None:
            rv = it.get("default_reward")
        if rv is None or not row.get("id"):
            continue
        reward_rows.append({
            "event_id":      row["id"],
            "user_id":       user_id,
            "module":        module,
            "event_type":    it["event_type"],
            "reward_value":  rv,
            "reward_source": "rule_engine",
        })
        total_delta += rv

    if reward_rows:
        try:
            await _to_thread(db.table("rewards").insert(reward_rows))
        except Exception as e:
            logger.error(f"[RewardEngine] Bulk reward insert failed: {e}")

    if total_delta:
        await update_module_cumulative_reward(user_id, module, total_delta)

    return len(inserted)
