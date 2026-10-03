"""
app/core/integrations/oauth_handler.py — OAuth Token Exchange & Refresh

Handles the full OAuth 2.0 flow for all CRM + Marketing platforms.
Exchanges authorization codes for tokens, stores per user, auto-refreshes.
"""

import os
import logging
import httpx
from datetime import datetime, timedelta, timezone
from app.database import get_supabase, q

logger = logging.getLogger(__name__)

# ── Platform Token Endpoints ──────────────────────────────────────────────
_TOKEN_ENDPOINTS = {
    "zoho"      : "https://accounts.zoho.com/oauth/v2/token",
    "hubspot"   : "https://api.hubapi.com/oauth/v1/token",
    "meta_ads"  : "https://graph.facebook.com/v18.0/oauth/access_token",
    "google_ads": "https://oauth2.googleapis.com/token",
}

_CLIENT_IDS = {
    "zoho"      : os.getenv("ZOHO_CLIENT_ID", ""),
    "hubspot"   : os.getenv("HUBSPOT_CLIENT_ID", ""),
    "meta_ads"  : os.getenv("META_APP_ID", ""),
    "google_ads": os.getenv("GOOGLE_CLIENT_ID", ""),
}

_CLIENT_SECRETS = {
    "zoho"      : os.getenv("ZOHO_CLIENT_SECRET", ""),
    "hubspot"   : os.getenv("HUBSPOT_CLIENT_SECRET", ""),
    "meta_ads"  : os.getenv("META_APP_SECRET", ""),
    "google_ads": os.getenv("GOOGLE_CLIENT_SECRET", ""),
}

REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI", "http://localhost:8000/api/v1/integrations/oauth/callback")


# ── Token Exchange ────────────────────────────────────────────────────────

async def exchange_code_for_tokens(
    platform: str, 
    code: str, 
    custom_client_id: str = None, 
    custom_client_secret: str = None
) -> dict | None:
    """
    Exchange an OAuth authorization code for access + refresh tokens.
    Uses user-provided credentials if available, otherwise falls back to system .env.
    """
    endpoint = _TOKEN_ENDPOINTS.get(platform)
    client_id = custom_client_id or _CLIENT_IDS.get(platform)
    client_secret = custom_client_secret or _CLIENT_SECRETS.get(platform)

    if not endpoint or not client_id or not client_secret:
        logger.error(f"[OAuth] Missing credentials for platform: {platform}")
        return None

    params = {
        "grant_type"   : "authorization_code",
        "client_id"    : client_id,
        "client_secret": client_secret,
        "redirect_uri" : REDIRECT_URI,
        "code"         : code,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Zoho uses POST with form params
            if platform == "zoho":
                resp = await client.post(endpoint, params=params)
            else:
                resp = await client.post(endpoint, data=params)

            resp.raise_for_status()
            token_data = resp.json()
            logger.info(f"[OAuth] Token exchange success for {platform}")
            return token_data

    except httpx.HTTPStatusError as e:
        logger.error(f"[OAuth] Token exchange failed [{platform}]: {e.response.status_code} — {e.response.text}")
        return None
    except Exception as e:
        logger.error(f"[OAuth] Token exchange error [{platform}]: {e}")
        return None


# ── Token Storage ─────────────────────────────────────────────────────────

async def store_oauth_tokens(
    user_id: str,
    module: str,
    platform: str,
    token_data: dict,
    custom_client_id: str = None,
    custom_client_secret: str = None,
) -> str | None:
    """
    Upsert an integration row with the OAuth tokens.
    Returns integration_id or None on failure.
    """
    db = get_supabase()

    # Calculate expiry time
    expires_in = token_data.get("expires_in", 3600)
    expires_at = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()

    config = {
        "access_token" : token_data.get("access_token", ""),
        "refresh_token": token_data.get("refresh_token", ""),
        "token_type"   : token_data.get("token_type", "Bearer"),
        "expires_at"   : expires_at,
        "scope"        : token_data.get("scope", ""),
        # Zoho-specific
        "api_domain"   : token_data.get("api_domain", ""),
        # Persistence for custom user-provided credentials (to allow auto-refresh)
        "custom_client_id": custom_client_id,
        "custom_client_secret": custom_client_secret,
    }

    try:
        # Check if integration already exists for this user+platform
        existing = (
            await q(db.table("integrations")
            .select("id")
            .eq("user_id", user_id)
            .eq("module", module)
            .eq("platform", platform))
        )

        if existing.data:
            # Update existing
            integration_id = existing.data[0]["id"]
            await q(db.table("integrations").update({
                "config"      : config,
                "status"      : "active",
                "last_sync_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", integration_id))
            logger.info(f"[OAuth] Updated tokens for {platform} user={user_id[:8]}")
        else:
            # Create new
            result = await q(db.table("integrations").insert({
                "user_id" : user_id,
                "module"  : module,
                "platform": platform,
                "type"    : "oauth",
                "label"   : f"{platform.replace('_', ' ').title()} (OAuth)",
                "status"  : "active",
                "config"  : config,
            }))
            integration_id = result.data[0]["id"] if result.data else None
            logger.info(f"[OAuth] Stored new tokens for {platform} user={user_id[:8]}")

        return integration_id

    except Exception as e:
        logger.error(f"[OAuth] Token storage failed [{platform}]: {e}")
        return None


# ── Token Refresh ─────────────────────────────────────────────────────────

async def get_valid_access_token(integration_id: str) -> str | None:
    """
    Get a valid access token for an integration.
    Auto-refreshes if expired. Returns None if refresh fails.
    """
    db = get_supabase()

    r = await q(db.table("integrations").select("platform, config, status").eq("id", integration_id))
    if not r.data or r.data[0]["status"] != "active":
        return None

    integration = r.data[0]
    platform = integration["platform"]
    config = integration.get("config", {})

    access_token = config.get("access_token", "")
    refresh_token = config.get("refresh_token", "")
    expires_at_str = config.get("expires_at", "")

    # Check if token is still valid (with 5 min buffer)
    if expires_at_str:
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            if datetime.utcnow() < expires_at - timedelta(minutes=5):
                return access_token  # Still valid
        except ValueError:
            pass

    # Token expired — refresh it
    if not refresh_token:
        logger.warning(f"[OAuth] No refresh token for integration {integration_id[:8]}")
        return None

    new_tokens = await _refresh_tokens(platform, refresh_token, config)
    if not new_tokens:
        return None

    # Update stored tokens
    expires_in = new_tokens.get("expires_in", 3600)
    new_expires_at = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()

    updated_config = {
        **config,
        "access_token": new_tokens.get("access_token", access_token),
        "expires_at"  : new_expires_at,
    }
    # Some platforms also return a new refresh token
    if new_tokens.get("refresh_token"):
        updated_config["refresh_token"] = new_tokens["refresh_token"]

    await q(db.table("integrations").update({"config": updated_config}).eq("id", integration_id))
    logger.info(f"[OAuth] Token refreshed for {platform} integration={integration_id[:8]}")
    return updated_config["access_token"]


async def _refresh_tokens(platform: str, refresh_token: str, config: dict = {}) -> dict | None:
    """Use a refresh token to obtain a new access token."""
    endpoint = _TOKEN_ENDPOINTS.get(platform)
    if not endpoint:
        return None

    params = {
        "grant_type"   : "refresh_token",
        "client_id"    : config.get("custom_client_id") or _CLIENT_IDS.get(platform, ""),
        "client_secret": config.get("custom_client_secret") or _CLIENT_SECRETS.get(platform, ""),
        "refresh_token": refresh_token,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            if platform == "zoho":
                resp = await client.post(endpoint, params=params)
            else:
                resp = await client.post(endpoint, data=params)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error(f"[OAuth] Refresh failed [{platform}]: {e}")
        return None
