"""
api/v1/profile.py — User Profile Endpoints

GET  /profile         — Get own profile (name, company, plan, role)
PATCH /profile        — Update own profile (name, company only)
GET  /profile/all     — Admin only: all user profiles

All routes are ADDITIVE — no existing endpoint is modified.
The profiles table is managed separately from auth.users.
"""

from fastapi import APIRouter, Depends, HTTPException
from app.auth.dependencies import get_current_user, get_admin_user
from app.database import get_supabase, q
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    company:   Optional[str] = None
    avatar_url: Optional[str] = None


# ── GET /profile — Current user's own profile ─────────────────────────────────

@router.get("")
async def get_my_profile(current_user: dict = Depends(get_current_user)):
    """Returns the profile for the currently logged-in user."""
    user_id = current_user["sub"]
    db = get_supabase()

    try:
        result = (
            await q(db.table("profiles")
            .select("*")
            .eq("id", user_id)
            .limit(1))
        )

        if result.data:
            return {"profile": result.data[0], "found": True}

        # Profile doesn't exist yet → create it on the fly (safety net)
        email = current_user.get("email", "")
        name  = current_user.get("user_metadata", {}).get("name", email)
        new_profile = {
            "id":        user_id,
            "full_name": name,
            # SECURITY: role is HARDCODED, never derived from JWT claims.
            # `user_metadata` is writable by the user themselves via
            # supabase.auth.updateUser(), so reading it here let anyone whose
            # profiles row was missing self-promote: set the claim, call
            # GET /api/v1/profile, and this safety net would write "admin"
            # into the source of truth using the SERVICE-ROLE key — bypassing
            # RLS completely. is_admin_user() is hardened against exactly this
            # claim (see auth/dependencies.py); reintroducing it here defeated
            # that. A safety net must never be able to escalate privilege.
            # Promotions go only through PATCH /profile/admin/{user_id}.
            "role":      "user",
            "plan":      "starter",
        }
        await q(db.table("profiles").upsert(new_profile, on_conflict="id"))
        return {"profile": new_profile, "found": False, "auto_created": True}

    except Exception as e:
        logger.error(f"[Profile] GET failed for {user_id[:8]}: {e}")
        raise HTTPException(status_code=500, detail="Could not load profile")


# ── PATCH /profile — Update own profile ──────────────────────────────────────

@router.patch("")
async def update_my_profile(
    body: ProfileUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update name, company, or avatar. Users cannot change their own role or plan."""
    user_id = current_user["sub"]
    db = get_supabase()

    updates = {}
    if body.full_name  is not None: updates["full_name"]  = body.full_name
    if body.company    is not None: updates["company"]    = body.company
    if body.avatar_url is not None: updates["avatar_url"] = body.avatar_url

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    from datetime import datetime, timezone
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()

    try:
        result = (
            await q(db.table("profiles")
            .update(updates)
            .eq("id", user_id))
        )
        saved = result.data[0] if result.data else {**updates, "id": user_id}
        logger.info(f"[Profile] Updated — user={user_id[:8]} fields={list(updates.keys())}")
        return {"status": "ok", "profile": saved}

    except Exception as e:
        logger.error(f"[Profile] PATCH failed for {user_id[:8]}: {e}")
        raise HTTPException(status_code=500, detail="Could not update profile")


# ── GET /profile/all — Admin: all user profiles ───────────────────────────────

@router.get("/all")
async def get_all_profiles(current_user: dict = Depends(get_admin_user)):
    """Admin only: returns all user profiles including name, company, plan, role."""
    db = get_supabase()

    try:
        result = (
            await q(db.table("profiles")
            .select("id, full_name, company, plan, role, avatar_url, created_at, updated_at")
            .order("created_at", desc=True))
        )
        profiles = result.data or []
        return {
            "profiles": profiles,
            "count":    len(profiles),
        }

    except Exception as e:
        logger.error(f"[Profile] GET /all failed: {e}")
        # Return empty list — never crash the admin page
        return {"profiles": [], "count": 0, "error": str(e)}


# ── PATCH /profile/admin/{user_id} — Admin: update any user's plan/role ──────

@router.patch("/admin/{user_id}")
async def admin_update_profile(
    user_id: str,
    body: dict,
    current_user: dict = Depends(get_admin_user),
):
    """Admin only: update plan or role for any user."""
    db = get_supabase()

    # Only allow safe fields via admin
    allowed = {"plan", "role", "full_name", "company"}
    updates = {k: v for k, v in body.items() if k in allowed}

    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    # Validate plan and role values
    if "plan" in updates and updates["plan"] not in {"starter", "growth", "enterprise"}:
        raise HTTPException(status_code=400, detail="plan must be: starter | growth | enterprise")
    if "role" in updates and updates["role"] not in {"user", "admin"}:
        raise HTTPException(status_code=400, detail="role must be: user | admin")

    from datetime import datetime, timezone
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()

    try:
        result = (
            await q(db.table("profiles")
            .update(updates)
            .eq("id", user_id))
        )
        saved = result.data[0] if result.data else {**updates, "id": user_id}
        logger.info(
            f"[Profile] Admin update — target={user_id[:8]} "
            f"by={current_user['sub'][:8]} fields={list(updates.keys())}"
        )
        return {"status": "ok", "profile": saved}

    except Exception as e:
        logger.error(f"[Profile] Admin PATCH failed: {e}")
        raise HTTPException(status_code=500, detail="Could not update profile")
