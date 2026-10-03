"""
api/v1/user_autonomy.py — User Self-Autonomy Control Endpoints

GET  /api/v1/user/autonomy  — Returns the current user's own autonomy settings
                              plus their plan's allowed levels (for frontend gating)
PATCH /api/v1/user/autonomy — Updates the current user's own settings
                              Validated against plan-based gates

ADDITIVE: All new endpoints. Uses get_current_user (NOT admin).
          Existing admin/autonomy endpoints are completely untouched.
          Falls back gracefully if user_autonomy_config table doesn't exist.
"""

from fastapi import APIRouter, Depends, HTTPException
from app.auth.dependencies import get_current_user
from app.database import get_supabase, q
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Plan-Based Autonomy Gates ─────────────────────────────────────────────────
# Controls what autonomy levels each plan tier can access.
# '__all__' means all modules are allowed for that level.
PLAN_GATES = {
    'starter': {
        'allowed_levels':  ['observe', 'assist'],
        'allowed_modules': '__all__',
        'description':     'Starter plan: Observe and Assist modes only',
    },
    # Key MUST match the values accepted by PATCH /profile/admin/{user_id}
    # (profile.py validates: starter | growth | enterprise). This was 'pro',
    # so get_plan_gate('growth') missed and silently fell back to the
    # restrictive starter gate — an upgraded customer kept starter limits and
    # the 'pro' gate was unreachable because nothing could ever write it.
    'growth': {
        'allowed_levels':  ['observe', 'assist', 'autonomous'],
        'allowed_modules': ['crm', 'marketing', 'website'],
        'description':     'Growth plan: Autonomous mode on CRM, Marketing, Website only',
    },
    'enterprise': {
        'allowed_levels':  ['observe', 'assist', 'autonomous'],
        'allowed_modules': '__all__',
        'description':     'Enterprise plan: Full access to all autonomy levels on all modules',
    },
}

# Default gate for unknown/missing plans (safe fallback = most restrictive)
DEFAULT_GATE = PLAN_GATES['starter']

ALL_MODULES = ['crm', 'marketing', 'shield', 'website']
VALID_LEVELS = {'observe', 'assist', 'autonomous'}


def get_plan_gate(plan: str) -> dict:
    """Return the gate config for a given plan tier."""
    return PLAN_GATES.get((plan or '').lower(), DEFAULT_GATE)


async def get_user_plan(db, user_id: str) -> str:
    """
    Fetch a user's plan tier from profiles, defaulting to the most restrictive
    tier on any failure.

    Shared so that every endpoint writing user_autonomy_config gates against
    the same value. POST /states/autonomy previously had no plan check at all,
    which let a starter-plan user grant themselves 'autonomous'.
    """
    try:
        res = await q(db.table("profiles").select("plan").eq("id", user_id).limit(1))
        if res.data:
            return res.data[0].get("plan") or "starter"
    except Exception as e:
        logger.warning(f"[Autonomy] Could not read plan for {str(user_id)[:8]}: {e} — using starter")
    return "starter"


def level_allowed(level: str, module: str, gate: dict) -> bool:
    """Check if a level is allowed for a module under the given gate."""
    if level not in gate['allowed_levels']:
        return False
    if gate['allowed_modules'] == '__all__':
        return True
    return module in gate['allowed_modules']


# ── Request Schema ────────────────────────────────────────────────────────────

class UserAutonomyUpdate(BaseModel):
    global_level: Optional[str] = None
    crm:          Optional[str] = None
    marketing:    Optional[str] = None
    shield:       Optional[str] = None
    website:      Optional[str] = None


# ── GET /user/autonomy ────────────────────────────────────────────────────────

@router.get("/autonomy")
async def get_my_autonomy(current_user: dict = Depends(get_current_user)):
    """
    Returns the current user's own autonomy settings AND their plan's allowed gates.
    The frontend uses plan_gates to render lock icons on disallowed options.
    """
    user_id = current_user.get("id") or current_user.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found in token")

    db = get_supabase()

    # ── 1. Get user's current autonomy config ─────────────────────────────────
    try:
        result = await q(db.table("user_autonomy_config").select("*").eq("user_id", user_id).single())
        config = result.data or {}
    except Exception:
        config = {}

    # ── 2. Get user's plan from profiles ─────────────────────────────────────
    try:
        profile_res = await q(db.table("profiles").select("plan, role").eq("id", user_id).single())
        profile = profile_res.data or {}
    except Exception:
        profile = {}

    plan = profile.get("plan") or "starter"
    role = profile.get("role") or "user"
    gate = get_plan_gate(plan)

    # Build per-module allowed map for frontend
    module_gates = {}
    for mod in ALL_MODULES:
        module_gates[mod] = {
            level: level_allowed(level, mod, gate)
            for level in ['observe', 'assist', 'autonomous']
        }

    return {
        "settings": {
            "global_level": config.get("global_level", "assist"),
            "crm":          config.get("crm",          "assist"),
            "marketing":    config.get("marketing",     "assist"),
            "shield":       config.get("shield",        "observe"),
            "website":      config.get("website",       "autonomous"),
        },
        "plan":        plan,
        "role":        role,
        "plan_gates": {
            "allowed_levels":  gate["allowed_levels"],
            "allowed_modules": gate["allowed_modules"],
            "description":     gate["description"],
            "module_gates":    module_gates,
        },
    }


# ── PATCH /user/autonomy ──────────────────────────────────────────────────────

@router.patch("/autonomy")
async def update_my_autonomy(
    body: UserAutonomyUpdate,
    current_user: dict = Depends(get_current_user),
):
    """
    Updates the current user's own autonomy settings.
    Validates each requested level against the user's plan gate.
    Admin override: if user has role='admin', all levels are allowed.
    """
    user_id = current_user.get("id") or current_user.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found in token")

    db = get_supabase()

    # ── 1. Get user's plan + role ─────────────────────────────────────────────
    try:
        profile_res = await q(db.table("profiles").select("plan, role").eq("id", user_id).single())
        profile = profile_res.data or {}
    except Exception:
        profile = {}

    plan = profile.get("plan") or "starter"
    role = profile.get("role") or "user"
    gate = get_plan_gate(plan)
    is_admin = (role == "admin")

    # ── 2. Validate each field against plan gates ─────────────────────────────
    updates = {}
    violations = []

    field_map = {
        "global_level": None,    # global level checked against all modules
        "crm":          "crm",
        "marketing":    "marketing",
        "shield":       "shield",
        "website":      "website",
    }

    for field, module in field_map.items():
        val = getattr(body, field, None)
        if val is None:
            continue
        if val not in VALID_LEVELS:
            raise HTTPException(status_code=422, detail=f"Invalid level '{val}' for '{field}'")

        # Admins bypass all gates
        if is_admin:
            updates[field] = val
            continue

        # Global level: validate against most permissive allowed module
        if field == "global_level":
            if val not in gate["allowed_levels"]:
                violations.append(f"global_level='{val}' not allowed on your {plan} plan")
            else:
                updates[field] = val
        else:
            if not level_allowed(val, module, gate):
                violations.append(f"{field}='{val}' not allowed on your {plan} plan (upgrade required)")
            else:
                updates[field] = val

    if violations:
        raise HTTPException(
            status_code=403,
            detail={"message": "Plan gate violation", "violations": violations, "plan": plan}
        )

    if not updates:
        return {"status": "no_changes", "message": "Nothing to update"}

    # ── 3. Upsert into user_autonomy_config ───────────────────────────────────
    try:
        updates["user_id"] = user_id
        await q(db.table("user_autonomy_config").upsert(updates, on_conflict="user_id"))
        logger.info(f"[UserAutonomy] User {user_id[:8]} updated autonomy: {updates}")
        return {"status": "ok", "updated": updates, "plan": plan}
    except Exception as e:
        logger.error(f"[UserAutonomy] Failed to save for {user_id[:8]}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save autonomy settings")
