"""
app/core/integrations/executor.py — L5 Decision Execution Engine

Sends approved AI decisions to external platforms via n8n webhooks.
Each platform has a registered n8n workflow that handles the actual API call.
This module is the bridge between NeuralOrbit decisions and real-world execution.
"""

import os
import logging
import httpx
from datetime import datetime

logger = logging.getLogger(__name__)

# ── n8n Webhook Registry ──────────────────────────────────────────────────
# Map: (module, action_type) → n8n webhook URL
# These are configured in n8n as separate workflows per action.
# Set the base URL via N8N_BASE_URL in .env
N8N_BASE = os.getenv("N8N_BASE_URL", "http://localhost:5678")

N8N_WEBHOOKS = {
    # CRM Actions
    ("crm", "assign_lead")         : f"{N8N_BASE}/webhook/crm-assign-lead",
    ("crm", "update_deal_stage")   : f"{N8N_BASE}/webhook/crm-update-deal",
    ("crm", "send_followup")       : f"{N8N_BASE}/webhook/crm-send-followup",
    ("crm", "create_task")         : f"{N8N_BASE}/webhook/crm-create-task",

    # Marketing Actions
    ("marketing", "pause_campaign"): f"{N8N_BASE}/webhook/marketing-pause-campaign",
    ("marketing", "adjust_budget") : f"{N8N_BASE}/webhook/marketing-adjust-budget",
    ("marketing", "pause_ad")      : f"{N8N_BASE}/webhook/marketing-pause-ad",

    # Website Actions
    ("website", "send_alert")      : f"{N8N_BASE}/webhook/website-alert",
    ("website", "notify_team")     : f"{N8N_BASE}/webhook/website-notify",

    # Shield Actions
    ("shield", "block_user")       : f"{N8N_BASE}/webhook/shield-block-user",
    ("shield", "send_alert")       : f"{N8N_BASE}/webhook/shield-alert",
    ("shield", "escalate")         : f"{N8N_BASE}/webhook/shield-escalate",
}


def get_registered_actions(module: str) -> list[str]:
    """Action codes registered for a module — single source of truth for
    both the executor's lookup table and the LLM prompt's allowed choices."""
    return [a for (m, a) in N8N_WEBHOOKS if m == module]


async def execute_decision(
    decision_id: str,
    module: str,
    action: str,
    parameters: dict,
    user_id: str,
    action_code: str | None = None,
) -> dict:
    """
    Execute an AI decision by triggering the appropriate n8n workflow.

    `action_code` is the structured code (e.g. "assign_lead") that decisions
    are now tagged with at creation time — see decisions.action_code. `action`
    is the free-text label stored for humans and always sent in the n8n
    payload for context. Lookup uses action_code when present; falls back to
    matching on `action` directly for older rows created before this column
    existed (which will almost always still be "no_webhook", same as before —
    this fix only helps decisions created after action_code was added).

    Returns: {"status": "executed"|"no_webhook"|"error", "detail": str}
    """
    key = (module, action_code) if action_code else (module, action)
    webhook_url = N8N_WEBHOOKS.get(key)

    if not webhook_url:
        logger.warning(f"[Executor] No n8n webhook for {module}/{action_code or action}")
        return {
            "status" : "no_webhook",
            "detail" : f"No workflow registered for action_code '{action_code}' in module '{module}'. "
                       f"Configure in n8n and add to executor.py.",
        }

    payload = {
        "decision_id" : decision_id,
        "module"      : module,
        "action"      : action,
        "action_code" : action_code,
        "parameters"  : parameters,
        "user_id"     : user_id,
        "triggered_at": datetime.utcnow().isoformat(),
        "source"      : "neuralorbit_ai",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(webhook_url, json=payload)
            resp.raise_for_status()
            logger.info(
                f"[Executor] ✓ Executed {module}/{action} "
                f"decision={decision_id[:8]} status={resp.status_code}"
            )
            return {
                "status"     : "executed",
                "detail"     : f"n8n workflow triggered: {action}",
                "n8n_status" : resp.status_code,
                "n8n_body"   : resp.text[:200],
            }
    except httpx.ConnectError:
        logger.error(f"[Executor] n8n not running at {N8N_BASE}")
        return {
            "status" : "error",
            "detail" : "n8n is not running. Start n8n and configure the workflow.",
        }
    except httpx.HTTPStatusError as e:
        logger.error(f"[Executor] n8n returned {e.response.status_code}")
        return {
            "status" : "error",
            "detail" : f"n8n workflow returned HTTP {e.response.status_code}",
        }
    except Exception as e:
        logger.error(f"[Executor] Unexpected error: {e}")
        return {"status": "error", "detail": str(e)}


def list_available_actions() -> list[dict]:
    """List all registered n8n actions (for the frontend decision UI)."""
    return [
        {"module": m, "action": a, "webhook": url}
        for (m, a), url in N8N_WEBHOOKS.items()
    ]
