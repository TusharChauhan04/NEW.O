"""
api/v1/admin_autonomy.py — Admin Autonomy Override Endpoints

GET  /admin/autonomy/heatmap        — All users × all modules matrix
PATCH /admin/autonomy/{user_id}     — Override per-module settings for a specific user
POST  /admin/autonomy/freeze-all    — Emergency: set ALL users, ALL modules to observe

ADDITIVE: Uses existing user_autonomy_config table (already exists).
          No existing endpoint or DB schema is modified.
"""

from fastapi import APIRouter, Depends, HTTPException
from app.auth.dependencies import get_admin_user
from app.database import get_supabase, q
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

_VALID_LEVELS   = {"observe", "assist", "autonomous"}
_ALL_MODULES    = ["global_level", "crm", "marketing", "shield", "website"]
_MODULE_DISPLAY = {
    "global_level": "Global",
    "crm":         "CRM",
    "marketing":   "Marketing",
    "shield":      "Shield",
    "website":     "Website",
}


class ModuleAutonomyOverride(BaseModel):
    global_level: Optional[str] = None
    crm:          Optional[str] = None
    marketing:    Optional[str] = None
    shield:       Optional[str] = None
    website:      Optional[str] = None


# ── GET /admin/autonomy/heatmap ───────────────────────────────────────────────

@router.get("/heatmap")
async def get_autonomy_heatmap(current_user: dict = Depends(get_admin_user)):
    """
    Returns a matrix of all users × all modules autonomy settings.
    Used by the admin Users page to render the autonomy heatmap grid.
    """
    db = get_supabase()
    try:
        result = (
            await q(db.table("user_autonomy_config")
            .select("user_id, global_level, crm, marketing, shield, website, updated_at")
            .order("updated_at", desc=True))
        )
        rows = result.data or []

        # Count how many users are in each level per module
        summary = {}
        for mod in _ALL_MODULES:
            counts = {"observe": 0, "assist": 0, "autonomous": 0}
            for r in rows:
                level = r.get(mod, "assist")
                if level in counts:
                    counts[level] += 1
            summary[mod] = counts

        return {
            "matrix":       rows,
            "total_users":  len(rows),
            "summary":      summary,
        }

    except Exception as e:
        logger.error(f"[AdminAutonomy] Heatmap error: {e}")
        return {"matrix": [], "total_users": 0, "summary": {}, "error": str(e)}


# ── PATCH /admin/autonomy/{user_id} ──────────────────────────────────────────

@router.patch("/{user_id}")
async def override_user_autonomy(
    user_id: str,
    body: ModuleAutonomyOverride,
    current_user: dict = Depends(get_admin_user),
):
    """
    Admin override: set one or more module autonomy levels for a specific user.
    Only updates fields that are provided — leaves others unchanged.
    """
    db = get_supabase()

    # Build the update dict — only include fields that were explicitly provided
    updates: dict = {}
    for mod in _ALL_MODULES:
        val = getattr(body, mod, None)
        if val is not None:
            if val not in _VALID_LEVELS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid level '{val}' for {mod}. Must be: observe | assist | autonomous"
                )
            updates[mod] = val

    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided to update")

    updates["updated_at"]  = datetime.now(timezone.utc).isoformat()
    updates["user_id"]     = user_id  # ensure present for upsert

    admin_id = current_user["sub"]

    try:
        # Upsert — creates record if user hasn't saved autonomy settings yet
        await q(db.table("user_autonomy_config").upsert(updates, on_conflict="user_id"))

        logger.info(
            f"[AdminAutonomy] Override — target={user_id[:8]} "
            f"by={admin_id[:8]} fields={list(updates.keys())}"
        )
        return {
            "status":  "ok",
            "user_id": user_id,
            "updated": {k: v for k, v in updates.items() if k not in ("user_id", "updated_at")},
        }

    except Exception as e:
        logger.error(f"[AdminAutonomy] Override failed: {e}")
        raise HTTPException(status_code=500, detail="Could not update autonomy settings")


# ── POST /admin/autonomy/freeze-all ──────────────────────────────────────────

@router.post("/freeze-all")
async def emergency_freeze_all(current_user: dict = Depends(get_admin_user)):
    """
    Emergency kill switch: sets ALL users, ALL modules to 'observe' mode.
    AI will stop generating autonomous actions for every user.

    This is a destructive operation — confirm this in the frontend before calling.
    """
    db       = get_supabase()
    admin_id = current_user["sub"]
    logger.warning(f"[AdminAutonomy] ⚠️ EMERGENCY FREEZE triggered by admin={admin_id[:8]}")

    try:
        # Fetch all user IDs that have autonomy configs
        result = await q(db.table("user_autonomy_config").select("user_id"))
        rows   = result.data or []

        if not rows:
            return {"status": "ok", "message": "No autonomy configs found to freeze", "users_frozen": 0}

        frozen = 0
        errors = 0
        now    = datetime.now(timezone.utc).isoformat()

        for row in rows:
            try:
                await q(db.table("user_autonomy_config").update({
                    "global_level": "observe",
                    "crm":          "observe",
                    "marketing":    "observe",
                    "shield":       "observe",
                    "website":      "observe",
                    "updated_at":   now,
                }).eq("user_id", row["user_id"]))
                frozen += 1
            except Exception:
                errors += 1

        logger.warning(
            f"[AdminAutonomy] Freeze complete — "
            f"frozen={frozen} errors={errors} by admin={admin_id[:8]}"
        )
        return {
            "status":       "ok",
            "message":      f"Emergency freeze applied. {frozen} users set to Observe mode.",
            "users_frozen": frozen,
            "errors":       errors,
            "frozen_by":    admin_id[:8],
            "frozen_at":    now,
        }

    except Exception as e:
        logger.error(f"[AdminAutonomy] Freeze-all failed: {e}")
        raise HTTPException(status_code=500, detail=f"Emergency freeze failed: {e}")
