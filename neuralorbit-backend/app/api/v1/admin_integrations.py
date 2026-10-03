"""
api/v1/admin_integrations.py — Admin Integration Health Endpoints

GET  /admin/integrations         — All integrations across all users, with event counts
GET  /admin/integrations/health  — Summary: active/broken/total per module

ADDITIVE: Reads from existing 'integrations' and 'raw_integration_events' tables.
          No existing endpoints, models, or DB tables are modified.
"""

from fastapi import APIRouter, Depends, HTTPException
from app.auth.dependencies import get_admin_user
from app.database import get_supabase, q
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# ── GET /admin/integrations ───────────────────────────────────────────────────

@router.get("")
async def get_all_integrations(current_user: dict = Depends(get_admin_user)):
    """
    Returns all integrations across all users.
    Enriches each row with:
      - event_count: how many raw events have been received
      - error_count: how many events failed to normalize
      - health: 'active' | 'error' | 'idle'
    """
    db = get_supabase()

    try:
        # Fetch all integrations (no user_id filter — admin sees everything)
        int_result = (
            await q(db.table("integrations")
            .select("id, user_id, module, platform, type, label, status, last_sync_at, created_at")
            .order("created_at", desc=True)
            .limit(500))
        )
        integrations = int_result.data or []

        if not integrations:
            return {"integrations": [], "total": 0, "health_summary": _empty_summary()}

        # Fetch event counts per integration (all raw_integration_events)
        try:
            raw_result = (
                await q(db.table("raw_integration_events")
                .select("integration_id, normalized, error"))
            )
            raw_events = raw_result.data or []
        except Exception:
            raw_events = []

        # Build lookup: integration_id → {total, errors}
        event_counts: dict[str, dict] = {}
        for ev in raw_events:
            iid = ev.get("integration_id") or ""
            bucket = event_counts.setdefault(iid, {"total": 0, "errors": 0})
            bucket["total"] += 1
            if ev.get("error"):
                bucket["errors"] += 1

        # Enrich integrations
        now = datetime.now(timezone.utc)
        for intg in integrations:
            iid     = intg.get("id") or ""
            bucket  = event_counts.get(iid, {"total": 0, "errors": 0})
            intg["event_count"] = bucket["total"]
            intg["error_count"] = bucket["errors"]

            # Derive health
            last_sync = intg.get("last_sync_at")
            if bucket["errors"] > 0 and bucket["errors"] >= bucket["total"]:
                intg["health"] = "error"
            elif intg.get("status") != "active":
                intg["health"] = "disconnected"
            elif last_sync:
                # "idle" if last sync was > 24 hours ago
                try:
                    delta = (now - datetime.fromisoformat(last_sync.replace("Z", "+00:00"))).total_seconds()
                    intg["health"] = "idle" if delta > 86400 else "active"
                except Exception:
                    intg["health"] = "active"
            else:
                intg["health"] = "idle"

        # Build health summary
        health_summary = {
            "total":        len(integrations),
            "active":       sum(1 for i in integrations if i["health"] == "active"),
            "idle":         sum(1 for i in integrations if i["health"] == "idle"),
            "error":        sum(1 for i in integrations if i["health"] == "error"),
            "disconnected": sum(1 for i in integrations if i["health"] == "disconnected"),
            "total_events": sum(i["event_count"] for i in integrations),
        }

        return {
            "integrations":    integrations,
            "total":           len(integrations),
            "health_summary":  health_summary,
        }

    except Exception as e:
        logger.error(f"[AdminIntegrations] List failed: {e}")
        return {"integrations": [], "total": 0, "health_summary": _empty_summary(), "error": str(e)}


# ── GET /admin/integrations/health ───────────────────────────────────────────

@router.get("/health")
async def get_integration_health(current_user: dict = Depends(get_admin_user)):
    """
    Returns a module-level health summary.
    e.g. { crm: { active: 2, error: 1, idle: 0 }, ... }
    """
    db = get_supabase()
    try:
        result = (
            await q(db.table("integrations")
            .select("module, status, last_sync_at"))
        )
        rows  = result.data or []
        mods  = {}
        for r in rows:
            m = r.get("module", "unknown")
            bucket = mods.setdefault(m, {"active": 0, "idle": 0, "total": 0})
            bucket["total"] += 1
            if r.get("status") == "active":
                bucket["active"] += 1
            else:
                bucket["idle"] += 1

        return {"by_module": mods, "total": len(rows)}
    except Exception as e:
        logger.error(f"[AdminIntegrations] Health summary failed: {e}")
        return {"by_module": {}, "total": 0, "error": str(e)}


def _empty_summary():
    return {"total": 0, "active": 0, "idle": 0, "error": 0, "disconnected": 0, "total_events": 0}
