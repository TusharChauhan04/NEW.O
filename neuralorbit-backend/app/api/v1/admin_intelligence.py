"""
api/v1/admin_intelligence.py — Admin AI Intelligence Dashboard Endpoints

GET /admin/intelligence/summary     — Cross-user accuracy + mistake leaderboard
GET /admin/intelligence/mistakes    — Top mistake patterns across all users
GET /admin/intelligence/accuracy    — Per-module accuracy breakdown (all users)

ADDITIVE: All new endpoints. No existing endpoint, DB table, or file is modified.
          Reads from learning_stats + mistake_patterns (both already created).
          Falls back gracefully if tables don't exist yet.
"""

from fastapi import APIRouter, Depends
from app.auth.dependencies import get_admin_user
from app.database import get_supabase, q
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# ── GET /admin/intelligence/summary ──────────────────────────────────────────

@router.get("/summary")
async def get_intelligence_summary(current_user: dict = Depends(get_admin_user)):
    """
    Returns high-level AI intelligence metrics across ALL users.
    Used by the Admin AI Intelligence dashboard top KPI cards.

    Returns:
        total_users_tracked: int
        avg_accuracy_pct: float (0-100)
        total_decisions: int
        total_mistakes_recorded: int
        top_module: str (highest avg accuracy)
        worst_module: str (lowest avg accuracy)
        auto_executed_today: int
    """
    try:
        db = get_supabase()

        # ── 1. Read learning_stats for all users ──────────────────────────────
        stats_result = await q(db.table("learning_stats").select(
            "user_id, module, accuracy_pct, total_decisions, rejected_decisions, updated_at"
        ))
        stats = stats_result.data or []

        if not stats:
            return _empty_summary()

        total_users     = len({s["user_id"] for s in stats})
        total_decisions = sum(s.get("total_decisions", 0) for s in stats)
        avg_accuracy    = round(
            sum(s.get("accuracy_pct", 0) for s in stats) / len(stats), 1
        ) if stats else 0.0

        # Per-module accuracy averages
        module_acc: dict[str, list] = {}
        for s in stats:
            m = s.get("module", "unknown")
            module_acc.setdefault(m, []).append(s.get("accuracy_pct", 0))
        module_avgs = {m: round(sum(v)/len(v), 1) for m, v in module_acc.items()}
        top_module   = max(module_avgs, key=module_avgs.get) if module_avgs else "—"
        worst_module = min(module_avgs, key=module_avgs.get) if module_avgs else "—"

        # ── 2. Count mistakes across all users ────────────────────────────────
        try:
            mistakes_result = await q(db.table("mistake_patterns").select("times_rejected"))
            total_mistakes = sum(m.get("times_rejected", 1) for m in (mistakes_result.data or []))
        except Exception:
            total_mistakes = 0

        # ── 3. Auto-executed today ────────────────────────────────────────────
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        try:
            auto_result = await q(db.table("decisions").select("id", count="exact").eq(
                "auto_executed", True
            ).gte("created_at", today_start))
            auto_executed_today = auto_result.count or 0
        except Exception:
            auto_executed_today = 0

        return {
            "total_users_tracked":   total_users,
            "avg_accuracy_pct":      avg_accuracy,
            "total_decisions":       total_decisions,
            "total_mistakes_recorded": total_mistakes,
            "top_module":            top_module,
            "worst_module":          worst_module,
            "auto_executed_today":   auto_executed_today,
            "module_accuracy":       module_avgs,
        }

    except Exception as e:
        logger.error(f"[AdminIntelligence] Summary failed: {e}")
        return _empty_summary()


def _empty_summary():
    return {
        "total_users_tracked":     0,
        "avg_accuracy_pct":        0.0,
        "total_decisions":         0,
        "total_mistakes_recorded": 0,
        "top_module":              "—",
        "worst_module":            "—",
        "auto_executed_today":     0,
        "module_accuracy":         {},
    }


# ── GET /admin/intelligence/mistakes ─────────────────────────────────────────

@router.get("/mistakes")
async def get_top_mistakes(
    limit: int = 20,
    current_user: dict = Depends(get_admin_user),
):
    """
    Returns the top N most-rejected AI recommendations across ALL users.
    Sorted by times_rejected descending.
    Admin sees which recommendations the AI keeps getting wrong.
    """
    try:
        db = get_supabase()
        result = (
            await q(db.table("mistake_patterns")
            .select("module, trigger_type, bad_action, times_rejected, last_seen_at, user_id")
            .order("times_rejected", desc=True)
            .limit(limit))
        )
        mistakes = result.data or []

        # Anonymize user_id for privacy (show only first 8 chars)
        for m in mistakes:
            uid = m.get("user_id", "")
            m["user_id"] = uid[:8] + "..." if uid else "—"

        return {"mistakes": mistakes, "total": len(mistakes)}

    except Exception as e:
        logger.error(f"[AdminIntelligence] Mistakes fetch failed: {e}")
        return {"mistakes": [], "total": 0}


# ── GET /admin/intelligence/accuracy ─────────────────────────────────────────

@router.get("/accuracy")
async def get_accuracy_breakdown(
    current_user: dict = Depends(get_admin_user),
):
    """
    Returns per-user per-module accuracy stats for the admin intelligence table.
    Sorted by accuracy_pct ascending (worst first, so admin can spot problems).
    """
    try:
        db = get_supabase()
        result = (
            await q(db.table("learning_stats")
            .select("user_id, module, accuracy_pct, total_decisions, correct_decisions, rejected_decisions, avg_confidence, updated_at")
            .order("accuracy_pct", desc=False)
            .limit(100))
        )
        rows = result.data or []

        # Anonymize user IDs
        for r in rows:
            uid = r.get("user_id", "")
            r["user_id"] = uid[:8] + "..." if uid else "—"

        return {"rows": rows, "total": len(rows)}

    except Exception as e:
        logger.error(f"[AdminIntelligence] Accuracy breakdown failed: {e}")
        return {"rows": [], "total": 0}
