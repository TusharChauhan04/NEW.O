"""
api/v1/tracking.py — NeuralOrbit Website Tracker Endpoint (L4)

POST /track   ← receives batched events from tracker.js on user websites
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Depends
from app.database import get_supabase, q
from app.auth.dependencies import get_current_user
from app.core.rate_limit import check_rate_limit
from app.core.intelligence.reward_engine import record_events_bulk
import logging, hashlib

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Reward map for website events ─────────────────────────────────────────
_REWARD_MAP = {
    "page_view"          : 1.0,
    "cta_click"          : 3.0,
    "form_submit"        : 10.0,
    "scroll_depth_75"    : 4.0,
    "scroll_depth_100"   : 6.0,
    "session_end_long"   : 8.0,   # >300s session
    "checkout_complete"  : 15.0,
    "session_end"        : 0.5,
}


async def _resolve_token(token: str) -> dict | None:
    """
    Lookup integration by hashed token → return {integration_id, user_id}

    Async because it runs two DB round-trips on the unauthenticated /track
    hot path. As a sync helper called from an async handler it blocked the
    event loop just as surely as a bare .execute() in the handler itself.
    """
    db = get_supabase()
    key_hash = hashlib.sha256(token.encode()).hexdigest()

    # Check api_keys first (most common for website tracker)
    r = await q(
        db.table("integration_api_keys")
        .select("id, user_id, integration_id, is_active")
        .eq("key_hash", key_hash)
        .eq("is_active", True)
    )
    if r.data:
        return {"user_id": r.data[0]["user_id"], "integration_id": r.data[0]["integration_id"]}

    # Fallback: check integration webhook_secret (for tracker-generated IDs)
    r2 = await q(
        db.table("integrations")
        .select("id, user_id")
        .eq("webhook_secret", token)
        .eq("status", "active")
    )
    if r2.data:
        return {"user_id": r2.data[0]["user_id"], "integration_id": r2.data[0]["id"]}

    return None


def _event_reward(evt: dict) -> tuple[str, float]:
    """Map tracker event to (event_type, reward_value)"""
    t = evt.get("type", "unknown")
    data = evt.get("data", {})

    if t == "scroll_depth":
        pct = data.get("pct", 0)
        if pct >= 100:   return "scroll_depth_full",   _REWARD_MAP["scroll_depth_100"]
        elif pct >= 75:  return "scroll_depth_high",   _REWARD_MAP["scroll_depth_75"]
        else:            return f"scroll_depth_{pct}",  1.0

    if t == "session_end":
        dur = data.get("duration_s", 0)
        if dur >= 300:   return "session_engaged",  _REWARD_MAP["session_end_long"]
        elif dur < 10:   return "session_bounce",   -3.0
        else:            return "session_end",       _REWARD_MAP["session_end"]

    return t, _REWARD_MAP.get(t, 1.0)


@router.post("")
async def receive_tracking_events(request: Request):
    """
    Receive batched tracking events from tracker.js running on a user's website.
    Validates token, normalizes events, and stores with reward scores.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    token = body.get("token", "")
    events = body.get("events", [])
    session_id = body.get("session_id", "")

    if not token:
        raise HTTPException(status_code=401, detail="Missing tracking token")
    if not events:
        return {"status": "ok", "accepted": 0}

    # Resolve token → user
    ctx = await _resolve_token(token)
    if not ctx:
        raise HTTPException(status_code=401, detail="Invalid or inactive tracking token")

    user_id = ctx["user_id"]
    integration_id = ctx["integration_id"]

    # This endpoint is unauthenticated by design (public website visitors) —
    # rate-limit per resolved integration so one token can't flood the table.
    check_rate_limit(f"track:{integration_id}", max_calls=120, window_seconds=60)

    db = get_supabase()
    total_reward = 0.0

    # Build every row first, then insert ONCE.
    # This loop previously issued one blocking round-trip per event — up to 50
    # per batch, ~1.5s of event-loop stall, on the highest-traffic and
    # unauthenticated endpoint in the system. The rate limit caps how OFTEN a
    # batch arrives, not what each one costs.
    rows = []
    for evt in events[:50]:   # cap at 50 events per batch
        try:
            # _event_reward dereferences fully client-controlled data
            # (data["pct"], data["duration_s"]). It used to sit OUTSIDE this
            # try, so a payload like {"data":{"pct":null}} raised TypeError,
            # returned an unhandled 500, and discarded the other 49 events.
            event_type, reward = _event_reward(evt)
        except Exception as e:
            logger.warning(f"[Track] Skipping malformed event: {e}")
            continue

        rows.append({
            "event_type": event_type,
            "payload": {
                "path"       : evt.get("path", ""),
                "session_id" : session_id,
                "referrer"   : evt.get("referrer", ""),
                "data"       : evt.get("data", {}),
            },
            # _REWARD_MAP is the FALLBACK now, not the source of truth. The
            # reward_config table wins when it has a matching row, so an admin
            # can retune website rewards without a redeploy.
            "default_reward": reward,
        })
        total_reward += reward

    accepted = 0
    if rows:
        try:
            # Routes through the shared pipeline so tracker traffic finally
            # writes `rewards` rows and updates module_states.cumulative_reward.
            # Previously this endpoint wrote events and stopped, so a customer
            # with the tracker installed still showed cumulative_reward = 0.
            # Still ONE insert round-trip for the batch.
            accepted = await record_events_bulk(
                user_id=user_id, module="website", items=rows, source="tracker",
            )
        except Exception as e:
            logger.error(f"[Track] Bulk insert of {len(rows)} events failed: {e}")
            raise HTTPException(status_code=500, detail="Could not store events")

    # Update integration last_sync
    await q(
        db.table("integrations").update(
            {"last_sync_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", integration_id)
    )

    logger.info(f"[Track] session={session_id[:12]} accepted={accepted} reward={total_reward:.1f}")
    return {"status": "ok", "accepted": accepted, "total_reward": total_reward}


@router.get("/snippet/{integration_id}")
async def get_tracker_snippet(
    integration_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Returns the personalised tracker snippet for a given integration_id.
    The token embedded is the integration's webhook_secret (single-use tracker key).

    SECURITY FIX: this previously had no auth dependency and no ownership
    check at all — anyone who knew or brute-forced an integration_id got
    that tenant's live tracking secret back in plaintext. Now requires a
    valid session and scopes the lookup to the caller's own integration,
    matching every other endpoint in this router.
    """
    user_id = current_user.get("sub") or current_user.get("id")
    db = get_supabase()
    r = (
        await q(db.table("integrations")
        .select("id, webhook_secret, module")
        .eq("id", integration_id)
        .eq("user_id", user_id)
        .eq("module", "website")
        .eq("status", "active"))
    )
    if not r.data:
        raise HTTPException(status_code=404, detail="Integration not found")

    token = r.data[0]["webhook_secret"]
    snippet = f"""<!-- NeuralOrbit Website Tracker -->
<script>
(function(w,d){{
  'use strict';
  var s=d.createElement('script');
  s.async=true;
  s.src='http://localhost:8000/static/tracker.js';
  s.dataset.token='{token}';
  d.head.appendChild(s);
}})(window,document);
</script>"""

    return {"snippet": snippet, "token": token}
