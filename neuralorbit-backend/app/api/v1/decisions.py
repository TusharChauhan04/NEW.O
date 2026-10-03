"""
api/v1/decisions.py — Decision Log Endpoints

POST   /decisions                   — Create a decision record manually
GET    /decisions                   — Fetch decisions (admin: all users, user: own)
PATCH  /decisions/{id}/outcome      — Mark a decision as applied/rejected/pending
POST   /decisions/{id}/override     — Toggle human override ON/OFF (persisted to DB)
POST   /decisions/{id}/execute      — (L5) Execute decision via n8n
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from app.auth.dependencies import get_current_user, get_admin_user, is_admin_user
from app.models.decision import DecisionCreate, DecisionOutcomeUpdate
from app.database import get_supabase, q
from app.core.constants import VALID_MODULES
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("", status_code=201)
async def create_decision(
    decision: DecisionCreate,
    current_user: dict = Depends(get_current_user),
):
    """Manually log an AI decision."""
    if decision.module not in VALID_MODULES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid module '{decision.module}'. Valid: {sorted(VALID_MODULES)}",
        )

    user_id = current_user["sub"]
    db = get_supabase()

    result = await q(db.table("decisions").insert({
        "user_id":        user_id,
        "module":         decision.module,
        "action":         decision.action,
        "action_code":    decision.action_code,
        "reasoning":      decision.reasoning,
        "confidence":     decision.confidence,
        "state_snapshot": decision.state_snapshot or {},
        "alternatives":   decision.alternatives or [],
        "outcome":        "pending",
    }))

    return {"status": "ok", "decision": result.data[0] if result.data else {}}


@router.get("")
async def get_decisions(
    module:  str | None = Query(None,  description="Filter by module"),
    outcome: str | None = Query(None,  description="Filter by outcome"),
    all:     bool       = Query(False, description="Admin only: return all users' decisions"),
    limit:   int        = Query(50,    ge=1, le=200),
    current_user: dict  = Depends(get_current_user),
):
    """
    Fetch decision log.
    - Admin + all=true  → all users' decisions (cross-client view)
    - Otherwise         → current user's decisions only
    """
    user_id  = current_user["sub"]
    is_admin = await is_admin_user(current_user)
    db       = get_supabase()

    query = (
        db.table("decisions")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
    )

    if not (is_admin and all):
        query = query.eq("user_id", user_id)

    if module:
        query = query.eq("module", module)
    if outcome:
        query = query.eq("outcome", outcome)

    result    = await q(query)
    decisions = result.data or []

    return {"decisions": decisions, "count": len(decisions)}


@router.patch("/{decision_id}/outcome")
async def update_outcome(
    decision_id: str,
    update: DecisionOutcomeUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Mark a decision as applied, rejected, or pending."""
    valid = {"applied", "rejected", "pending"}
    if update.outcome not in valid:
        raise HTTPException(
            status_code=400,
            detail=f"outcome must be one of: {sorted(valid)}",
        )

    user_id  = current_user["sub"]
    is_admin = await is_admin_user(current_user)
    db       = get_supabase()

    query = (
        db.table("decisions")
        .update({"outcome": update.outcome})
        .eq("id", decision_id)
    )
    if not is_admin:
        query = query.eq("user_id", user_id)

    result = await q(query)

    if not result.data:
        raise HTTPException(status_code=404, detail="Decision not found")

    logger.info(
        f"[Decisions] Outcome → {update.outcome} "
        f"decision={decision_id[:8]} user={user_id[:8]}"
    )

    # ── Learning Signal (non-blocking) ───────────────────────────────────────
    # Fires AFTER the outcome is already committed to DB.
    # Wrapped in try/except — if learning engine fails, this endpoint still
    # returns the correct response. Zero impact on existing behaviour.
    try:
        from app.core.intelligence.learning_engine import update_learning_stats
        dec = result.data[0]
        await update_learning_stats(
            user_id    = user_id,
            module     = dec.get("module", "neural-orbit"),
            outcome    = update.outcome,
            confidence = float(dec.get("confidence") or 0.0),
        )
    except Exception as _le:
        logger.warning(f"[Decisions] Learning signal skipped (non-critical): {_le}")
    # ── End Learning Signal ───────────────────────────────────────────────────

    return {"status": "ok", "decision": result.data[0]}


@router.post("/{decision_id}/override")
async def toggle_override(
    decision_id: str,
    enabled:     bool = Query(..., description="True = human override ON, False = revert to AI"),
    current_user: dict = Depends(get_current_user),
):
    """
    Toggle human override for a decision (persisted to DB).
    - Admin: can override any user's decision
    - User:  can only override their own decisions
    """
    user_id  = current_user["sub"]
    is_admin = await is_admin_user(current_user)
    db       = get_supabase()

    update_data = {
        "override_enabled": enabled,
        "override_by":      user_id,
        "outcome":          "rejected" if enabled else "pending",
    }

    query = db.table("decisions").update(update_data).eq("id", decision_id)
    if not is_admin:
        query = query.eq("user_id", user_id)

    result = await q(query)

    if not result.data:
        raise HTTPException(status_code=404, detail="Decision not found or access denied")

    logger.info(
        f"[Decisions] Override {'ON' if enabled else 'OFF'} — "
        f"decision={decision_id[:8]} by={user_id[:8]}"
    )
    return {"status": "ok", "override_enabled": enabled, "decision": result.data[0]}


@router.post("/{decision_id}/execute")
async def execute_decision(
    decision_id: str,
    current_user: dict = Depends(get_admin_user),
):
    """
    L5 — Execute an approved AI decision via n8n. Admin only.

    SECURITY: the dependency is `get_admin_user`, not `get_current_user`.
    Previously the docstring claimed "Admin only" but the code only used the
    admin flag to widen the row lookup — there was no 403. Any user could
    POST /decisions with a chosen action_code and state_snapshot, then call
    this endpoint to fire a real n8n workflow with attacker-chosen parameters.
    (No SSRF: the n8n URL registry in executor.py is a fixed dict. The missing
    control was the human-approval gate on real-world actions.)

    NOTE — product decision: this enforces the documented admin-only contract,
    which is the fail-closed reading. If the intent is that users may execute
    their OWN approved decisions, change the dependency back to
    `get_current_user`, restore the `.eq("user_id", user_id)` scoping below,
    and gate on the user's autonomy level instead.
    """
    from app.core.integrations.executor import execute_decision as run_executor

    user_id  = current_user["sub"]
    db       = get_supabase()

    # Admin-only endpoint, so no per-user scoping is applied to the lookup.
    query = db.table("decisions").select("*").eq("id", decision_id)
    r = await q(query)

    if not r.data:
        raise HTTPException(status_code=404, detail="Decision not found")

    dec = r.data[0]
    if dec.get("outcome") == "rejected":
        raise HTTPException(status_code=400, detail="Cannot execute a rejected decision")

    result = await run_executor(
        decision_id = decision_id,
        module      = dec.get("module", ""),
        action      = dec.get("action", ""),
        action_code = dec.get("action_code"),
        parameters  = dec.get("state_snapshot", {}),
        user_id     = dec.get("user_id", user_id),
    )

    if result["status"] == "executed":
        await q(db.table("decisions").update({"outcome": "applied"}).eq("id", decision_id))

    logger.info(f"[Decisions/Execute] {result['status']} — decision={decision_id[:8]}")
    return {
        "status"     : result["status"],
        "detail"     : result["detail"],
        "decision_id": decision_id,
    }
