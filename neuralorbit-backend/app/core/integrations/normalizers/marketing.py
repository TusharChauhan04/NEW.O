"""
app/core/integrations/normalizers/marketing.py — L3 Marketing Event Normalizer

Maps raw Meta Ads / Google Ads webhook payloads to NeuralOrbit event schema.
"""

import logging
logger = logging.getLogger(__name__)

# ── Reward definitions (Marketing module) ──────────────────────────────────
MARKETING_REWARD_MAP = {
    "ad_conversion"        : 13.0,
    "ctr_increase"         :  6.0,
    "cpa_decrease"         :  8.0,
    "roas_improvement"     : 10.0,
    "ad_fatigue_detected"  : -5.0,
    "budget_waste"         : -8.0,
    "campaign_started"     :  2.0,
    "campaign_paused"      :  1.0,
    "ad_impression"        :  0.1,
    "ad_click"             :  1.0,
    "lead_from_ad"         :  8.0,
    "purchase_from_ad"     : 15.0,
}


# ── Meta Ads ───────────────────────────────────────────────────────────────
def normalize_meta(payload: dict) -> list[dict]:
    """
    Meta sends Real-time Updates (Webhooks):
    {"entry": [{"changes": [{"field": "adAccount", "value": {...}}]}]}
    """
    events = []
    entries = payload.get("entry", [payload])

    for entry in entries:
        changes = entry.get("changes", [{"value": entry}])
        for change in changes:
            value  = change.get("value", {})
            field  = change.get("field", "")

            # Lead ad form submit → strong buying signal
            if field == "leadgen" or "leadgen" in str(payload):
                events.append({
                    "event_type"  : "lead_from_ad",
                    "reward_value": MARKETING_REWARD_MAP["lead_from_ad"],
                    "payload"     : value,
                    "source"      : "meta_ads",
                })
                continue

            # Conversion pixel fire
            conv = value.get("conversion") or value.get("event_name", "")
            if "purchase" in str(conv).lower():
                events.append({
                    "event_type"  : "purchase_from_ad",
                    "reward_value": MARKETING_REWARD_MAP["purchase_from_ad"],
                    "payload"     : value,
                    "source"      : "meta_ads",
                })
            elif conv:
                events.append({
                    "event_type"  : "ad_conversion",
                    "reward_value": MARKETING_REWARD_MAP["ad_conversion"],
                    "payload"     : value,
                    "source"      : "meta_ads",
                })

    return events


# ── Google Ads ─────────────────────────────────────────────────────────────
def normalize_google_ads(payload: dict) -> list[dict]:
    """
    Google Ads doesn't have native webhooks — data comes via n8n polling.
    Expects normalized payload: {"metric": "...", "value": ..., "campaign_id": "..."}
    """
    events = []
    metric = payload.get("metric", "").lower()
    value  = payload.get("value")

    metric_map = {
        "conversion"        : ("ad_conversion",    MARKETING_REWARD_MAP["ad_conversion"]),
        "ctr_delta"         : ("ctr_increase",     MARKETING_REWARD_MAP["ctr_increase"]),
        "cpa_delta"         : ("cpa_decrease",     MARKETING_REWARD_MAP["cpa_decrease"]),
        "roas_delta"        : ("roas_improvement", MARKETING_REWARD_MAP["roas_improvement"]),
        "impression_share"  : ("ad_impression",    MARKETING_REWARD_MAP["ad_impression"]),
    }

    if metric in metric_map:
        event_type, base_reward = metric_map[metric]
        reward = base_reward
        # Scale reward by value magnitude if positive/negative
        if isinstance(value, (int, float)):
            reward = base_reward * (1 + min(abs(value) / 100.0, 2.0))
            if value < 0 and event_type not in ("cpa_decrease",):
                reward = -abs(reward)

        events.append({
            "event_type"  : event_type,
            "reward_value": round(reward, 2),
            "payload"     : payload,
            "source"      : "google_ads",
        })

    return events


def normalize_marketing_event(platform: str, payload: dict) -> list[dict]:
    """Route to the correct normalizer."""
    if platform == "meta_ads":    return normalize_meta(payload)
    if platform == "google_ads":  return normalize_google_ads(payload)
    logger.warning(f"[Marketing Normalizer] Unknown platform: {platform}")
    return []
