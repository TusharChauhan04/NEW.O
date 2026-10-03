"""
app/core/integrations/crm_sync.py — CRM Data Sync Workers

Pulls real contact/deal data from connected CRM platforms (Zoho, Custom)
and stores them as NeuralOrbit events in the database.
Each sync is fully isolated per user (user_id scoped).

Safety: Read-only calls to external APIs. No destructive operations.
"""

import logging
import httpx
from datetime import datetime
from app.database import get_supabase, q
from app.core.integrations.normalizers.crm import normalize_crm_event

from app.core.intelligence.reward_engine import record_event

logger = logging.getLogger(__name__)

# ── Timeout for all external API calls ───────────────────────────────────────
_API_TIMEOUT = 15.0


# ── Zoho CRM Sync ─────────────────────────────────────────────────────────────

DEFAULT_ZOHO_BASE = "https://www.zohoapis.com"

# Zoho serves each data centre from its own domain. Anything outside this set
# is rejected rather than trusted.
_ALLOWED_ZOHO_SUFFIXES = (
    ".zohoapis.com", ".zohoapis.eu", ".zohoapis.in",
    ".zohoapis.com.au", ".zohoapis.jp", ".zohoapis.ca", ".zohoapis.sa",
)


def _safe_zoho_base(api_domain: str) -> str:
    """
    Validate a user-supplied Zoho API domain, falling back to the default.

    Rejects anything that is not https:// on an allowlisted Zoho host. This
    closes an SSRF: `api_domain` lives in integrations.config, which a user can
    write directly via PostgREST under the own_integrations RLS policy, and it
    was previously interpolated straight into an authenticated outbound
    request — reaching e.g. http://169.254.169.254 cloud metadata.
    """
    from urllib.parse import urlparse

    candidate = (api_domain or "").strip().rstrip("/")
    if not candidate:
        return DEFAULT_ZOHO_BASE

    parsed = urlparse(candidate)
    if parsed.scheme != "https":
        logger.warning(f"[CRM Sync] Rejected non-https api_domain: {candidate[:60]!r}")
        return DEFAULT_ZOHO_BASE

    host = (parsed.hostname or "").lower()
    if host != "zohoapis.com" and not host.endswith(_ALLOWED_ZOHO_SUFFIXES):
        logger.warning(f"[CRM Sync] Rejected non-Zoho api_domain host: {host!r}")
        return DEFAULT_ZOHO_BASE

    # Rebuild from parsed parts so any path/query/fragment is discarded.
    return f"https://{host}"


async def sync_zoho(user_id: str, integration_id: str, access_token: str, api_domain: str = "") -> dict:
    """
    Pull contacts and deals from Zoho CRM, normalize them, and write
    NeuralOrbit events to the database.

    Returns: { "synced": N, "errors": M, "platform": "zoho" }
    """
    # SECURITY (SSRF): api_domain comes from integrations.config, which a user
    # can write directly through PostgREST — the RLS policy
    # `own_integrations FOR ALL USING (auth.uid() = user_id)` permits it, so no
    # backend endpoint has to allow it. Unvalidated, setting
    #     config.api_domain = "http://169.254.169.254/latest"
    # made the server issue an AUTHENTICATED request (the OAuth bearer token is
    # attached below) to the cloud metadata endpoint. Allowlist the host.
    base = _safe_zoho_base(api_domain)
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json",
    }

    synced = 0
    errors = 0

    # Modules we want to pull from Zoho
    zoho_modules = [
        {"endpoint": f"{base}/crm/v2/Contacts", "module_name": "contacts"},
        {"endpoint": f"{base}/crm/v2/Deals",    "module_name": "deals"},
        {"endpoint": f"{base}/crm/v2/Leads",    "module_name": "leads"},
    ]

    db = get_supabase()

    async with httpx.AsyncClient(timeout=_API_TIMEOUT) as client:
        for mod in zoho_modules:
            try:
                resp = await client.get(
                    mod["endpoint"],
                    headers=headers,
                    params={"per_page": 100, "sort_by": "Modified_Time", "sort_order": "desc"},
                )

                if resp.status_code == 204:
                    # No records — skip silently
                    continue

                if resp.status_code == 401:
                    logger.warning(f"[CRM Sync] Zoho token expired for user={user_id[:8]}")
                    errors += 1
                    continue

                resp.raise_for_status()
                data = resp.json()
                records = data.get("data", [])

                # Build a Zoho-style webhook payload for the existing normalizer
                normalized_payload = {
                    "operation": "insert",
                    "module": mod["module_name"],
                    "data": records,
                }

                events = normalize_crm_event("zoho", normalized_payload)

                # Route through the shared pipeline. This path had NO reward
                # handling at all — it wrote events and stopped — so a customer
                # with a live Zoho integration accrued zero cumulative_reward
                # no matter how much real CRM activity synced.
                for ev in events:
                    try:
                        await record_event(
                            user_id       = user_id,
                            module        = "crm",
                            event_type    = ev["event_type"],
                            payload       = ev.get("payload", {}),
                            source        = "zoho",
                            default_reward= ev.get("reward_value"),
                        )
                        synced += 1
                    except Exception as db_err:
                        logger.error(f"[CRM Sync] DB write error: {db_err}")
                        errors += 1

            except httpx.HTTPStatusError as e:
                logger.error(f"[CRM Sync] Zoho API error [{mod['module_name']}]: {e.response.status_code}")
                errors += 1
            except Exception as e:
                logger.error(f"[CRM Sync] Unexpected error [{mod['module_name']}]: {e}")
                errors += 1

    # Update last_sync_at timestamp on the integration row
    try:
        await q(db.table("integrations").update({
            "last_sync_at": datetime.utcnow().isoformat(),
        }).eq("id", integration_id))
    except Exception as e:
        logger.warning(f"[CRM Sync] Could not update last_sync_at: {e}")

    logger.info(f"[CRM Sync] Zoho sync complete — user={user_id[:8]} synced={synced} errors={errors}")
    return {"synced": synced, "errors": errors, "platform": "zoho"}


# ── Custom CRM / Webhook Sync ─────────────────────────────────────────────────

async def sync_custom(user_id: str, integration_id: str) -> dict:
    """
    For Custom CRM (webhook/API key mode), there is no active pull possible —
    data comes inbound via the webhook endpoint. This function simply returns
    a summary of events already in the database for this user.
    """
    db = get_supabase()

    try:
        result = (
            await q(db.table("events")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("module", "crm"))
        )
        count = result.count or 0
        logger.info(f"[CRM Sync] Custom CRM status — user={user_id[:8]} events={count}")
        return {
            "synced": count,
            "errors": 0,
            "platform": "custom",
            "note": "Custom CRM data comes via inbound webhook. No active pull needed."
        }
    except Exception as e:
        logger.error(f"[CRM Sync] Custom status check failed: {e}")
        return {"synced": 0, "errors": 1, "platform": "custom"}


# ── Dispatcher ────────────────────────────────────────────────────────────────

async def run_crm_sync(user_id: str, integration: dict) -> dict:
    """
    Main sync dispatcher. Routes to the correct sync worker
    based on the integration's platform.

    Args:
        user_id:     Supabase user UUID
        integration: Full integration row from DB (includes config dict)

    Returns dict with synced/errors counts.
    """
    platform = integration.get("platform", "")
    config   = integration.get("config", {})
    int_id   = integration.get("id", "")

    if platform == "zoho":
        api_domain = config.get("api_domain", "")

        # Use the refresh-aware accessor rather than the raw stored token.
        # get_valid_access_token() checks expiry (with a 5-minute buffer) and
        # transparently refreshes. It existed but had ZERO call sites, so this
        # path read config["access_token"] directly with no expiry check —
        # meaning every sync after the first hour failed with a 401 while a
        # perfectly good refresh token sat unused in the same config row.
        from app.core.integrations.oauth_handler import get_valid_access_token
        access_token = await get_valid_access_token(int_id)

        if not access_token:
            logger.error(f"[CRM Sync] No valid access_token for Zoho integration={int_id[:8]}")
            return {
                "synced": 0, "errors": 1, "platform": "zoho",
                "error": "Access token missing or refresh failed. Please reconnect.",
            }

        return await sync_zoho(user_id, int_id, access_token, api_domain)

    elif platform in ("custom", "webhook"):
        return await sync_custom(user_id, int_id)

    else:
        logger.warning(f"[CRM Sync] Unknown platform: {platform}")
        return {"synced": 0, "errors": 0, "platform": platform, "note": "No sync needed for this platform type."}
