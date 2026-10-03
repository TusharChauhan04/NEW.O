"""
api/v1/events.py — Event Tracking Endpoints

POST /events     — Log a business event (auto-calculates reward)
GET  /events     — Fetch events for current user, optionally filtered by module
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from app.auth.dependencies import get_current_user
from app.models.event import EventCreate
from app.database import get_supabase, q
from app.core.intelligence.reward_engine import record_event
from app.core.constants import VALID_MODULES
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("", status_code=201)
async def log_event(
    event: EventCreate,
    current_user: dict = Depends(get_current_user),
):
    """
    Log a business event and automatically score its reward.

    Example:
        POST /api/v1/events
        { "module": "crm", "event_type": "meeting_booked", "payload": {"lead_id": "abc"} }
    """
    if event.module not in VALID_MODULES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid module '{event.module}'. Valid: {sorted(VALID_MODULES)}",
        )

    user_id = current_user["sub"]

    # This handler used to BE the reward pipeline, inline. That inline copy was
    # the reason the other three ingest paths drifted: there was nothing to
    # reuse. The logic now lives in reward_engine.record_event and every writer
    # calls it, so there is one place where rewards are resolved and
    # module_states is updated.
    event_data = await record_event(
        user_id    = user_id,
        module     = event.module,
        event_type = event.event_type,
        payload    = event.payload or {},
        context    = event.context or {},
        source     = event.source,
    )
    reward_value = event_data.get("reward_value")

    logger.info(
        f"[Events] Logged {event.module}/{event.event_type} "
        + (f"reward={reward_value:+.1f}" if reward_value is not None else "(no reward config)")
        + f" user={user_id[:8]}"
    )

    return {
        "status": "ok",
        "event": event_data,
        "reward_applied": reward_value,
    }


@router.get("")
async def get_events(
    module: str | None = Query(None, description="Filter by module"),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    """Fetch recent events for the authenticated user."""
    user_id = current_user["sub"]
    db = get_supabase()

    query = (
        db.table("events")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
    )
    if module:
        query = query.eq("module", module)

    result = await q(query)
    events = result.data or []

    return {"events": events, "count": len(events)}
