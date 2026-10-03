"""
api/v1/rewards.py — Reward System Endpoints

GET  /rewards/config        — View saved reward weights for current user (or target user for admin)
POST /rewards/config        — Save reward weight configuration (admin can save for any user)
GET  /rewards/config/history— Admin only: change log for reward config
GET  /rewards/summary       — Reward totals, averages, and module breakdown
POST /rewards/manual        — Admin-only: manually assign a reward score
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from app.auth.dependencies import get_current_user, get_admin_user, is_admin_user
from app.models.reward import ManualRewardCreate
from app.database import get_supabase, q
from app.core.intelligence.reward_engine import DEFAULT_REWARD_CONFIG
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Pydantic models ────────────────────────────────────────────────────────────

class WeightConfigSave(BaseModel):
    conversion:    int            # 0–100
    retention:     int            # 0–100
    cost:          int            # 0–100
    risk:          int            # 0–100
    industry:      str = "SaaS"  # SaaS | Finance | E-commerce | Healthcare
    sim_mode:      bool = True    # True = simulation (safe), False = live
    target_user_id: Optional[str] = None  # Admin only: apply for another user


# ── Default weights ─────────────────────────────────────────────────────────────

_DEFAULT_WEIGHTS = {"conversion": 75, "retention": 85, "cost": 40, "risk": 30,
                    "industry": "SaaS", "sim_mode": True}


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/config")
async def get_reward_config(
    target_user_id: Optional[str] = Query(None, description="Admin only: fetch config for another user"),
    current_user: dict = Depends(get_current_user),
):
    """
    Return saved reward weight configuration.
    - Admin: can fetch config for any user via target_user_id
    - User:  always returns their own config
    Falls back to smart defaults if no config saved yet.
    """
    is_admin = await is_admin_user(current_user)
    user_id  = target_user_id if (is_admin and target_user_id) else current_user["sub"]
    db       = get_supabase()

    try:
        result = (
            await q(db.table("user_reward_config")
            .select("*")
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .limit(1))
        )

        if result.data:
            cfg = result.data[0]
            return {
                "config": {
                    "conversion": cfg.get("conversion", _DEFAULT_WEIGHTS["conversion"]),
                    "retention":  cfg.get("retention",  _DEFAULT_WEIGHTS["retention"]),
                    "cost":       cfg.get("cost",        _DEFAULT_WEIGHTS["cost"]),
                    "risk":       cfg.get("risk",        _DEFAULT_WEIGHTS["risk"]),
                    "industry":   cfg.get("industry",    _DEFAULT_WEIGHTS["industry"]),
                    "sim_mode":   cfg.get("sim_mode",    _DEFAULT_WEIGHTS["sim_mode"]),
                    "updated_at": cfg.get("updated_at"),
                    "updated_by": cfg.get("updated_by"),
                },
                "is_default": False,
                "user_id": user_id,
            }

        # No saved config — return defaults
        return {"config": _DEFAULT_WEIGHTS, "is_default": True, "user_id": user_id}

    except Exception as e:
        logger.warning(f"[Rewards] Could not load weight config: {e}")
        return {"config": _DEFAULT_WEIGHTS, "is_default": True, "user_id": user_id}


@router.post("/config")
async def save_reward_config(
    body: WeightConfigSave,
    current_user: dict = Depends(get_current_user),
):
    """
    Save reward weight configuration.
    - Admin: can save for any user by passing target_user_id in body
    - User:  saves for themselves only
    """
    is_admin = await is_admin_user(current_user)
    caller_id = current_user["sub"]
    user_id   = body.target_user_id if (is_admin and body.target_user_id) else caller_id

    db = get_supabase()

    record = {
        "user_id":    user_id,
        "conversion": max(0, min(100, body.conversion)),
        "retention":  max(0, min(100, body.retention)),
        "cost":       max(0, min(100, body.cost)),
        "risk":       max(0, min(100, body.risk)),
        "industry":   body.industry,
        "sim_mode":   body.sim_mode,
        "updated_by": caller_id,
    }

    try:
        # Upsert: update if exists, insert if not
        result = (
            await q(db.table("user_reward_config")
            .upsert(record, on_conflict="user_id"))
        )
        saved = result.data[0] if result.data else record

        logger.info(
            f"[Rewards] Config saved — user={user_id[:8]} "
            f"industry={body.industry} sim={body.sim_mode} by={caller_id[:8]}"
        )
        return {"status": "ok", "config": saved}

    except Exception as e:
        logger.error(f"[Rewards] Failed to save config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save config: {str(e)}")


@router.get("/config/history")
async def get_config_history(
    target_user_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_admin_user),  # Admin only
):
    """Admin only: view change history for reward config."""
    db = get_supabase()

    try:
        query = (
            db.table("user_reward_config_history")
            .select("*")
            .order("changed_at", desc=True)
            .limit(limit)
        )
        if target_user_id:
            query = query.eq("user_id", target_user_id)

        result = await q(query)
        return {"history": result.data or [], "count": len(result.data or [])}
    except Exception as e:
        logger.warning(f"[Rewards] History table not found: {e}")
        return {"history": [], "count": 0}


@router.get("/summary")
async def get_reward_summary(
    module: str | None = Query(None, description="Filter by module"),
    current_user: dict = Depends(get_current_user),
):
    """Reward summary — totals, averages, per-module breakdown, recent entries."""
    user_id = current_user["sub"]
    db = get_supabase()

    query = (
        db.table("rewards")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(200)
    )
    if module:
        query = query.eq("module", module)

    result = await q(query)
    data = result.data or []

    total = sum(r["reward_value"] for r in data)
    avg = round(total / len(data), 2) if data else 0.0

    by_module: dict = {}
    for r in data:
        m = r["module"]
        if m not in by_module:
            by_module[m] = {"total": 0.0, "count": 0, "avg": 0.0}
        by_module[m]["total"] = round(by_module[m]["total"] + r["reward_value"], 2)
        by_module[m]["count"] += 1

    for m_data in by_module.values():
        m_data["avg"] = round(m_data["total"] / m_data["count"], 2)

    return {
        "total_reward": round(total, 2),
        "event_count":  len(data),
        "avg_reward":   avg,
        "by_module":    by_module,
        "recent":       data[:10],
    }


@router.post("/manual", status_code=201)
async def add_manual_reward(
    reward: ManualRewardCreate,
    current_user: dict = Depends(get_admin_user),
):
    """Admin-only: manually assign a reward score to a module/event-type."""
    user_id = current_user["sub"]
    db = get_supabase()

    result = await q(db.table("rewards").insert({
        "user_id":       user_id,
        "module":        reward.module,
        "event_type":    reward.event_type,
        "reward_value":  reward.reward_value,
        "reward_source": "manual",
        "notes":         reward.notes,
    }))

    logger.info(
        f"[Rewards] Manual reward added — {reward.module}/{reward.event_type} "
        f"value={reward.reward_value:+.1f} user={user_id[:8]}"
    )
    return {"status": "ok", "reward": result.data[0] if result.data else {}}
