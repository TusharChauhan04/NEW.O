"""
core/intelligence/learning_engine.py — NeuralOrbit AI Learning Engine

Processes feedback signals from user approve/reject actions on AI decisions.
Tracks per-module accuracy, confidence trends, and improvement velocity.

This file is ADDITIVE — it reads from existing tables (decisions) and writes
to a new table (learning_stats). It never modifies any existing table schema.

Called from: decisions.py → update_outcome (non-blocking, wrapped in try/except)
"""

from app.database import get_supabase, q
from datetime import datetime, timezone, timedelta
import asyncio
import logging

logger = logging.getLogger(__name__)


# ── Core Learning Signal ───────────────────────────────────────────────────────

async def update_learning_stats(
    user_id:     str,
    module:      str,
    outcome:     str,       # "applied" | "rejected" | "pending"
    confidence:  float,     # 0.0 – 1.0 from the decision record
    decision_id: str = "",  # optional — used to record mistake pattern on rejection
) -> None:
    """
    Called every time a user approves or rejects an AI decision.
    Updates the running accuracy stats for (user_id, module) in learning_stats.

    SAFE: Wrapped in try/except at the call site in decisions.py.
          If this fails, the original outcome update is already committed.

    What counts as correct:
      - "applied"  → user accepted the AI recommendation → AI was right ✓
      - "rejected" → user rejected it                    → AI was wrong ✗
      - "pending"  → no signal yet, skip silently
    """
    if outcome == "pending":
        return  # No learning signal from pending decisions

    is_correct = (outcome == "applied")

    try:
        db = get_supabase()

        # ── Read existing stats row (or create defaults) ──────────────────────
        existing = (
            await q(db.table("learning_stats")
            .select("*")
            .eq("user_id", user_id)
            .eq("module", module))
        )

        if existing.data:
            row = existing.data[0]
            total     = row.get("total_decisions", 0) + 1
            correct   = row.get("correct_decisions", 0) + (1 if is_correct else 0)
            rejected  = row.get("rejected_decisions", 0) + (0 if is_correct else 1)
            old_avg_conf = row.get("avg_confidence", 0.0)
            old_total    = total - 1  # before this update
            # Running average for confidence
            new_avg_conf = round(
                ((old_avg_conf * old_total) + confidence) / total, 4
            ) if total > 0 else confidence

            scored = correct + rejected  # only count applied + rejected
            accuracy = round((correct / scored) * 100, 2) if scored > 0 else 0.0

            await q(db.table("learning_stats").update({
                "total_decisions":    total,
                "correct_decisions":  correct,
                "rejected_decisions": rejected,
                "accuracy_pct":       accuracy,
                "avg_confidence":     new_avg_conf,
                "last_decision_at":   datetime.now(timezone.utc).isoformat(),
                "updated_at":         datetime.now(timezone.utc).isoformat(),
            }).eq("user_id", user_id).eq("module", module))

        else:
            # First decision ever for this user+module
            scored    = 1
            correct   = 1 if is_correct else 0
            rejected  = 0 if is_correct else 1
            accuracy  = 100.0 if is_correct else 0.0

            await q(db.table("learning_stats").insert({
                "user_id":            user_id,
                "module":             module,
                "total_decisions":    1,
                "correct_decisions":  correct,
                "rejected_decisions": rejected,
                "accuracy_pct":       accuracy,
                "avg_confidence":     round(confidence, 4),
                "last_decision_at":   datetime.now(timezone.utc).isoformat(),
                "updated_at":         datetime.now(timezone.utc).isoformat(),
            }))

        logger.info(
            f"[LearningEngine] Signal recorded — "
            f"user={user_id[:8]} module={module} "
            f"outcome={outcome} correct={is_correct} confidence={confidence:.2f}"
        )

        # ── Record mistake pattern if this was a rejection ──────────────────
        if outcome == "rejected" and decision_id:
            await _record_mistake_pattern(user_id, module, decision_id)

    except Exception as e:
        logger.error(f"[LearningEngine] Failed to update stats: {e}")
        raise  # Let the caller's try/except handle it gracefully


# ── Mistake Pattern Recording ───────────────────────────────────────────────

async def _record_mistake_pattern(user_id: str, module: str, decision_id: str) -> None:
    """
    Called when a user rejects a decision.
    Upserts into mistake_patterns: increments times_rejected if row already exists.

    SAFE: Wrapped in its own try/except. If this fails, the stats update
          above is already committed and the user sees no error.
    """
    try:
        db = get_supabase()

        # Fetch the rejected decision to get action + trigger type
        dec = (
            await q(db.table("decisions")
            .select("action, state_snapshot, confidence")
            .eq("id", decision_id)
            .limit(1))
        )
        if not dec.data:
            return  # Decision not found — skip silently

        d            = dec.data[0]
        action       = d.get("action", "")
        snapshot     = d.get("state_snapshot") or {}
        trigger_type = snapshot.get("trigger", "unknown")

        if not action:
            return  # No action to record

        # Upsert: if row exists increment times_rejected, else create new row
        # Supabase upsert on_conflict handles the increment via merge logic
        existing = (
            await q(db.table("mistake_patterns")
            .select("id, times_rejected")
            .eq("user_id", user_id)
            .eq("module", module)
            .eq("trigger_type", trigger_type)
            .eq("bad_action", action)
            .limit(1))
        )

        now_iso = datetime.now(timezone.utc).isoformat()

        if existing.data:
            # Row exists — increment counter
            row_id      = existing.data[0]["id"]
            prev_count  = existing.data[0].get("times_rejected", 1)
            await q(db.table("mistake_patterns").update({
                "times_rejected": prev_count + 1,
                "last_seen_at":   now_iso,
            }).eq("id", row_id))
            logger.info(
                f"[LearningEngine] Mistake incremented — "
                f"{module}/{trigger_type} x{prev_count + 1} user={user_id[:8]}"
            )
        else:
            # First rejection for this trigger+action combo
            await q(db.table("mistake_patterns").insert({
                "user_id":          user_id,
                "module":           module,
                "trigger_type":     trigger_type,
                "bad_action":       action,
                "context_snapshot": snapshot,
                "times_rejected":   1,
                "last_seen_at":     now_iso,
                "created_at":       now_iso,
            }))
            logger.info(
                f"[LearningEngine] New mistake pattern recorded — "
                f"{module}/{trigger_type} user={user_id[:8]}"
            )

    except Exception as e:
        # Non-critical: stats update already succeeded above
        logger.warning(f"[LearningEngine] Mistake pattern recording skipped: {e}")


# ── Accuracy Trend (Day-by-day) ────────────────────────────────────────────────

async def get_accuracy_trend(
    user_id: str,
    module: str,
    days: int = 30,
) -> list[dict]:
    """
    Returns daily accuracy trend for the last N days.
    Built from the decisions table — no new tables needed for trend.

    Returns: [{"date": "2026-04-01", "accuracy": 72.5, "decisions": 4}, ...]
    """
    try:
        db = get_supabase()
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        result = (
            await q(db.table("decisions")
            .select("outcome, confidence, created_at")
            .eq("user_id", user_id)
            .eq("module", module)
            .in_("outcome", ["applied", "rejected"])
            .gte("created_at", since)
            .order("created_at", desc=False))
        )

        decisions = result.data or []
        if not decisions:
            return []

        # Group by date
        day_map: dict[str, dict] = {}
        for dec in decisions:
            date_str = dec["created_at"][:10]  # "2026-04-01"
            if date_str not in day_map:
                day_map[date_str] = {"correct": 0, "total": 0}
            day_map[date_str]["total"] += 1
            if dec["outcome"] == "applied":
                day_map[date_str]["correct"] += 1

        trend = []
        for date_str in sorted(day_map.keys()):
            d = day_map[date_str]
            accuracy = round((d["correct"] / d["total"]) * 100, 1) if d["total"] > 0 else 0.0
            trend.append({
                "date":      date_str,
                "accuracy":  accuracy,
                "decisions": d["total"],
                "correct":   d["correct"],
            })

        return trend

    except Exception as e:
        logger.error(f"[LearningEngine] Failed to get accuracy trend: {e}")
        return []


# ── All-Module Accuracy Summary ────────────────────────────────────────────────

async def get_all_module_accuracy(user_id: str) -> list[dict]:
    """
    Returns accuracy stats for all modules this user has decisions in.
    Used by the Learning dashboard for the per-module breakdown.

    Returns: [{"module": "crm", "accuracy_pct": 78.5, "total_decisions": 24, ...}]
    """
    try:
        db = get_supabase()
        result = (
            await q(db.table("learning_stats")
            .select("*")
            .eq("user_id", user_id)
            .order("accuracy_pct", desc=True))
        )
        return result.data or []

    except Exception as e:
        logger.error(f"[LearningEngine] Failed to get all module accuracy: {e}")
        return []


# ── Learning Velocity ──────────────────────────────────────────────────────────

async def get_learning_velocity(user_id: str, module: str) -> dict:
    """
    Computes how fast accuracy is improving.
    Compares accuracy in the last 7 days vs. the 7 days before that.

    Returns: {"velocity": +12.5, "label": "Improving", "recent_accuracy": 78.0, "prev_accuracy": 65.5}
    """
    try:
        now  = datetime.now(timezone.utc)
        day7  = (now - timedelta(days=7)).isoformat()
        day14 = (now - timedelta(days=14)).isoformat()

        db = get_supabase()

        def _fetch_accuracy(since: str, until: str) -> float:
            r = (
                db.table("decisions")
                .select("outcome")
                .eq("user_id", user_id)
                .eq("module", module)
                .in_("outcome", ["applied", "rejected"])
                .gte("created_at", since)
                .lt("created_at", until)
                .execute()
            )
            data = r.data or []
            if not data:
                return 0.0
            correct = sum(1 for d in data if d["outcome"] == "applied")
            return round((correct / len(data)) * 100, 1)

        # Bug #7 Fix: _fetch_accuracy() is a sync function.
        # Wrap in asyncio.to_thread() to avoid blocking the event loop.
        recent_acc = await asyncio.to_thread(_fetch_accuracy, day7,  now.isoformat())
        prev_acc   = await asyncio.to_thread(_fetch_accuracy, day14, day7)
        velocity   = round(recent_acc - prev_acc, 1)

        if velocity > 0:
            label = "Improving"
        elif velocity < 0:
            label = "Declining"
        else:
            label = "Stable"

        return {
            "velocity":        velocity,
            "label":           label,
            "recent_accuracy": recent_acc,
            "prev_accuracy":   prev_acc,
            "period":          "7-day vs previous 7-day",
        }

    except Exception as e:
        logger.error(f"[LearningEngine] Failed to compute velocity: {e}")
        return {"velocity": 0.0, "label": "Unknown", "recent_accuracy": 0.0, "prev_accuracy": 0.0}
