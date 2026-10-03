"""
api/v1/states.py — Module State & Autonomy Endpoints

GET  /states/all              — All module states for current user
GET  /states/autonomy         — Current autonomy settings (admin: all clients, user: own)
POST /states/autonomy         — Save autonomy settings
GET  /states/autonomy/clients — Admin only: all clients + their autonomy status
GET  /states/{module}         — State for a specific module
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from app.auth.dependencies import get_current_user, get_admin_user, is_admin_user
from app.core.intelligence.state_engine import get_module_state, get_all_module_states
from app.database import get_supabase, q
# Plan gating lives in user_autonomy.py; import it rather than duplicating so
# both write paths to user_autonomy_config enforce identically.
from app.api.v1.user_autonomy import get_plan_gate, level_allowed, get_user_plan
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Pydantic models ────────────────────────────────────────────────────────────

class AutonomySave(BaseModel):
    global_level:   str = "assist"   # observe | assist | autonomous
    crm:            str = "assist"
    marketing:      str = "assist"
    shield:         str = "observe"
    website:        str = "autonomous"
    locked_modules: list[str] = []    # Admin: lock these modules for the user
    target_user_id: Optional[str] = None  # Admin only: save for another user


_VALID_LEVELS  = {"observe", "assist", "autonomous"}
_DEFAULT_AUTO  = {"global_level": "assist", "crm": "assist",
                  "marketing": "assist", "shield": "observe",
                  "website": "autonomous", "locked_modules": []}


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/all")
async def get_all_states(current_user: dict = Depends(get_current_user)):
    """Get AI states for ALL modules — used by the NeuralOrbit overview dashboard."""
    user_id = current_user["sub"]
    states = await get_all_module_states(user_id)
    return {"status": "ok", "states": states, "count": len(states)}


@router.get("/autonomy")
async def get_autonomy(
    target_user_id: Optional[str] = Query(None, description="Admin only: fetch for another user"),
    current_user: dict = Depends(get_current_user),
):
    """
    Get saved autonomy settings.
    - Admin + target_user_id → fetch settings for that client
    - Admin without target    → fetch admin's own + list of all client levels
    - User                    → own settings only (locked modules included)
    """
    is_admin = await is_admin_user(current_user)
    user_id  = target_user_id if (is_admin and target_user_id) else current_user["sub"]
    db       = get_supabase()

    try:
        result = (
            await q(db.table("user_autonomy_config")
            .select("*")
            .eq("user_id", user_id)
            .limit(1))
        )

        if result.data:
            cfg = result.data[0]
            return {
                "autonomy":    {k: cfg.get(k, _DEFAULT_AUTO[k]) for k in _DEFAULT_AUTO},
                "is_default":  False,
                "user_id":     user_id,
            }

        return {"autonomy": _DEFAULT_AUTO, "is_default": True, "user_id": user_id}

    except Exception as e:
        logger.warning(f"[States] Could not load autonomy config: {e}")
        return {"autonomy": _DEFAULT_AUTO, "is_default": True, "user_id": user_id}


@router.post("/autonomy")
async def save_autonomy(
    body: AutonomySave,
    current_user: dict = Depends(get_current_user),
):
    """
    Save autonomy settings.
    - Admin: can save for any user (target_user_id), can lock modules
    - User:  saves own settings only, cannot modify locked modules
    """
    is_admin  = await is_admin_user(current_user)
    caller_id = current_user["sub"]
    user_id   = body.target_user_id if (is_admin and body.target_user_id) else caller_id
    db        = get_supabase()

    # Validate levels
    for field, value in [
        ("global_level", body.global_level), ("crm", body.crm),
        ("marketing", body.marketing), ("shield", body.shield), ("website", body.website)
    ]:
        if value not in _VALID_LEVELS:
            raise HTTPException(
                status_code=400,
                detail=f"'{field}' must be one of: {sorted(_VALID_LEVELS)}"
            )

    # ── Non-admin callers: enforce plan gates AND module locks ────────────
    # This endpoint writes the SAME user_autonomy_config row as
    # PATCH /api/v1/user/autonomy, but historically validated only the
    # vocabulary — so a starter-plan user could POST here and grant themselves
    # 'autonomous', which the other endpoint would have rejected. Because
    # decision_generator reads this level and auto-executes n8n workflows at
    # confidence >= 0.90, that turned a billing gate into live external
    # automation. Both endpoints must enforce identically.
    incoming = {
        "global_level": body.global_level,
        "crm":          body.crm,
        "marketing":    body.marketing,
        "shield":       body.shield,
        "website":      body.website,
    }

    if not is_admin:
        try:
            existing = (
                await q(db.table("user_autonomy_config")
                .select("locked_modules")
                .eq("user_id", user_id)
                .limit(1))
            )
            existing_row = existing.data[0] if existing.data else {}
            locked = existing_row.get("locked_modules", []) or []
        except Exception:
            existing_row, locked = {}, []

        # Plan gate — same helpers the /user/autonomy endpoint uses.
        plan = await get_user_plan(db, user_id)
        gate = get_plan_gate(plan)
        for module, level in incoming.items():
            check_module = "crm" if module == "global_level" else module
            if not level_allowed(level, check_module, gate):
                raise HTTPException(
                    status_code=403,
                    detail=(
                        f"'{level}' is not available for '{module}' on your "
                        f"{plan} plan (upgrade required)."
                    ),
                )

        # Module locks — previously the locked list was only carried forward
        # into the column, never compared against the incoming levels, so admin
        # module locking did nothing against this endpoint. Any locked module
        # now keeps its stored value.
        for module in list(incoming):
            if module in locked:
                if module in existing_row:
                    incoming[module] = existing_row[module]
                else:
                    raise HTTPException(
                        status_code=403,
                        detail=f"'{module}' is locked by an administrator and cannot be changed.",
                    )
    else:
        locked = body.locked_modules   # Admin sets the locked list

    record = {
        "user_id":       user_id,
        "global_level":  incoming["global_level"],
        "crm":           incoming["crm"],
        "marketing":     incoming["marketing"],
        "shield":        incoming["shield"],
        "website":       incoming["website"],
        "locked_modules": locked,
        "updated_by":    caller_id,
    }

    try:
        result = (
            await q(db.table("user_autonomy_config")
            .upsert(record, on_conflict="user_id"))
        )
        saved = result.data[0] if result.data else record

        logger.info(
            f"[States] Autonomy saved — user={user_id[:8]} global={body.global_level} "
            f"by={caller_id[:8]}"
        )
        return {"status": "ok", "autonomy": saved}

    except Exception as e:
        logger.error(f"[States] Failed to save autonomy: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save: {str(e)}")


@router.get("/autonomy/clients")
async def get_all_client_autonomy(
    current_user: dict = Depends(get_admin_user),  # Admin only
):
    """Admin only: get autonomy status for ALL clients including their name/email."""
    db = get_supabase()

    try:
        # Step 1: get all configured autonomy rows
        result = (
            await q(db.table("user_autonomy_config")
            .select("user_id, global_level, crm, marketing, shield, website, updated_at"))
        )
        configs = {row["user_id"]: row for row in (result.data or [])}

        # Step 2: fetch real user metadata via Supabase admin API
        try:
            users_resp = db.auth.admin.list_users()
            # Supabase returns a list of user objects
            user_list = users_resp if isinstance(users_resp, list) else getattr(users_resp, 'users', [])
        except Exception as e:
            logger.warning(f"[States] Could not list auth users: {e}")
            user_list = []

        # Step 3: merge — prefer configured users, supplement with all auth users
        client_map = {}

        # Add all auth users first
        for u in user_list:
            uid = getattr(u, 'id', None) or (u.get('id') if isinstance(u, dict) else None)
            if not uid:
                continue
            email = getattr(u, 'email', '') or (u.get('email', '') if isinstance(u, dict) else '')
            meta  = getattr(u, 'user_metadata', {}) or (u.get('user_metadata', {}) if isinstance(u, dict) else {})
            name  = meta.get('full_name') or meta.get('name') or email.split('@')[0] if email else uid[:8]
            client_map[uid] = {
                "id":           uid,
                "email":        email,
                "name":         name,
                "global_level": configs.get(uid, {}).get("global_level", "assist"),
                "crm":          configs.get(uid, {}).get("crm", "assist"),
                "marketing":    configs.get(uid, {}).get("marketing", "assist"),
                "shield":       configs.get(uid, {}).get("shield", "observe"),
                "website":      configs.get(uid, {}).get("website", "autonomous"),
                "updated_at":   configs.get(uid, {}).get("updated_at"),
            }

        # Also include any users with configs but not in auth list (edge case)
        for uid, cfg in configs.items():
            if uid not in client_map:
                client_map[uid] = {
                    "id":           uid,
                    "email":        uid[:12] + "...",
                    "name":         "User " + uid[:6],
                    "global_level": cfg.get("global_level", "assist"),
                    "crm":          cfg.get("crm", "assist"),
                    "marketing":    cfg.get("marketing", "assist"),
                    "shield":       cfg.get("shield", "observe"),
                    "website":      cfg.get("website", "autonomous"),
                    "updated_at":   cfg.get("updated_at"),
                }

        clients = list(client_map.values())
        return {"clients": clients, "count": len(clients)}

    except Exception as e:
        logger.warning(f"[States] Could not load client autonomy list: {e}")
        return {"clients": [], "count": 0}


@router.get("/{module}")
async def get_state(module: str, current_user: dict = Depends(get_current_user)):
    """Get current AI state for a specific module."""
    user_id = current_user["sub"]
    state = await get_module_state(user_id, module)
    return {"status": "ok", "state": state}
