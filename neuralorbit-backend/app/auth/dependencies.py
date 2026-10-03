"""
auth/dependencies.py — FastAPI Auth Dependencies
Validates Supabase JWTs on every protected route.
AUTH_REQUIRED=false bypasses auth entirely for local dev.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from app.config import settings
import logging

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

# ── Dev user used when AUTH_REQUIRED=false ─────────────────────────────────
# NOTE: sub MUST be a valid UUID — the DB columns are type `uuid`
_DEV_USER = {
    "sub": "00000000-0000-0000-0000-000000000001",   # valid UUID for dev admin
    "email": "admin@neuralorbit.ai",
    "role": "authenticated",
    "app_metadata": {"role": "admin"},
    "user_metadata": {"role": "admin", "name": "Dev Admin"},
}


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    """Validate JWT — or return dev user if AUTH_REQUIRED=false."""

    if not settings.AUTH_REQUIRED:
        return _DEV_USER

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide a Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
        if not payload.get("sub"):
            raise HTTPException(status_code=401, detail="Invalid token: missing sub")
        return payload

    except JWTError as e:
        logger.warning(f"[Auth] JWT validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def is_admin_user(current_user: dict) -> bool:
    """DB-backed admin check that returns a bool instead of raising.

    Source of truth = profiles table (controlled via SQL / admin API).
    JWT claims are NOT used for role on a real token — the top-level `role`
    claim on a genuine Supabase JWT is always "authenticated", never the
    app-level role, so callers must not check `current_user["role"]` directly.
    Falls back to JWT claims only in dev mode / when the DB is unreachable.

    Use this (not `get_admin_user`) in routes that serve both regular users
    and admins from the same endpoint (e.g. "show all users' data if admin,
    else just mine") — `get_admin_user` is for routes that are admin-only.
    """
    user_id = current_user.get("sub") or current_user.get("id")

    # ── Auth enforced: the profiles table is the ONLY source of truth ──────
    # This path deliberately FAILS CLOSED. Previously a DB error (or a missing
    # profiles row) fell through to JWT claims, which included
    # `user_metadata.role`. That claim is writable by the user themselves via
    # supabase.auth.updateUser(), so any Supabase outage became a privilege-
    # escalation window: set your own metadata to role=admin and wait.
    # Denying admin during an outage is the safe failure mode.
    if settings.AUTH_REQUIRED:
        if not user_id:
            return False
        try:
            from app.database import get_supabase, q
            db = get_supabase()
            # Off the event loop: this runs on EVERY authenticated request, so
            # blocking here serialized the entire service (see database.q).
            result = await q(
                db.table("profiles")
                .select("role")
                .eq("id", user_id)
                .limit(1)
            )
            if not result.data:
                logger.warning(f"[Auth] No profiles row for user {str(user_id)[:8]} — denying admin")
                return False
            return result.data[0].get("role", "user") == "admin"
        except Exception as e:
            logger.error(f"[Auth] profiles lookup failed: {e} — denying admin (fail closed)")
            return False

    # ── Dev mode only (AUTH_REQUIRED=False) ───────────────────────────────
    # Never consulted when auth is enforced. Only `app_metadata` is trusted
    # here: unlike `user_metadata`, it cannot be modified by the user, only by
    # an admin/service-role call.
    return current_user.get("app_metadata", {}).get("role") == "admin"


async def get_admin_user(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Require admin role — for routes that are admin-only end to end."""
    if not await is_admin_user(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user

