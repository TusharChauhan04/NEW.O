"""
app/core/integrations/normalizers/crm.py — L2 CRM Event Normalizer

Maps raw Zoho CRM / HubSpot webhook payloads to NeuralOrbit event schema.
Auto-scores rewards based on the Reward Framework config.
"""

import logging
logger = logging.getLogger(__name__)

# ── Reward definitions (from Reward Framework doc) ─────────────────────────
CRM_REWARD_MAP = {
    "deal_closed":         21.0,
    "meeting_booked":       8.0,
    "proposal_sent":        5.0,
    "follow_up_completed":  3.0,
    "lead_created":         2.0,
    "lead_qualified":       5.0,
    "lead_assigned":        1.0,
    "contact_created":      1.0,
    "deal_updated":         1.0,
    "lead_churn":         -10.0,
    "deal_lost":           -8.0,
    "no_response_7d":      -5.0,
}


# ── Zoho CRM ───────────────────────────────────────────────────────────────
def normalize_zoho(payload: dict) -> list[dict]:
    """
    Zoho sends: {"operation": "insert"|"update"|"delete", "module": "Deals", "data": [...]}
    Returns list of normalized NeuralOrbit events.
    """
    events = []
    operation = payload.get("operation", "")
    module    = payload.get("module", "").lower()
    data_list = payload.get("data", [payload])  # fallback: whole payload

    for record in data_list:
        event_type = None

        if module == "deals":
            stage = record.get("Stage", record.get("stage", "")).lower()
            if operation == "insert":
                event_type = "lead_created"
            elif "closed won" in stage or "won" in stage:
                event_type = "deal_closed"
            elif "closed lost" in stage or "lost" in stage:
                event_type = "deal_lost"
            else:
                event_type = "deal_updated"

        elif module in ("leads", "contacts"):
            if operation == "insert":
                event_type = "lead_created"
            elif record.get("Converted") or record.get("converted"):
                event_type = "lead_qualified"
            else:
                event_type = "contact_created"

        elif module == "calls" or module == "meetings":
            event_type = "meeting_booked"

        if event_type:
            events.append({
                "event_type"  : event_type,
                "reward_value": CRM_REWARD_MAP.get(event_type, 1.0),
                "payload"     : record,
                "source"      : "zoho",
            })

    return events


# ── HubSpot ────────────────────────────────────────────────────────────────
def normalize_hubspot(payload: dict) -> list[dict]:
    """
    HubSpot sends: [{"subscriptionType": "deal.creation", "objectId": 123, ...}]
    Returns list of normalized NeuralOrbit events.
    """
    events = []
    items  = payload if isinstance(payload, list) else [payload]

    _hs_map = {
        "deal.creation"              : "lead_created",
        "deal.propertyChange"        : "deal_updated",
        "contact.creation"           : "contact_created",
        "deal.deletion"              : "deal_lost",
        "meeting.creation"           : "meeting_booked",
        "ticket.creation"            : "lead_created",
    }

    for item in items:
        sub_type   = item.get("subscriptionType", "")
        prop       = item.get("propertyName", "")
        prop_val   = item.get("propertyValue", "")

        event_type = _hs_map.get(sub_type)

        # Detect closed won from property change
        if sub_type == "deal.propertyChange" and prop == "dealstage":
            if "closedwon" in str(prop_val).lower():
                event_type = "deal_closed"
            elif "closedlost" in str(prop_val).lower():
                event_type = "deal_lost"

        if event_type:
            events.append({
                "event_type"  : event_type,
                "reward_value": CRM_REWARD_MAP.get(event_type, 1.0),
                "payload"     : item,
                "source"      : "hubspot",
            })

    return events


# ── Dispatcher ────────────────────────────────────────────────────────────
def normalize_crm_event(platform: str, payload: dict) -> list[dict]:
    """Route to the correct normalizer based on platform."""
    if platform == "zoho":      return normalize_zoho(payload)
    if platform == "hubspot":   return normalize_hubspot(payload)
    logger.warning(f"[CRM Normalizer] Unknown platform: {platform}")
    return []
