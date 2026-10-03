"""
core/intelligence/state_engine.py — Module State Management

Reads the current AI state for a user+module combination.
Also fetches recent events and reward history for LLM context building.
"""

from app.database import get_supabase, q
import logging

logger = logging.getLogger(__name__)


async def get_module_state(user_id: str, module: str) -> dict:
    """Get the current AI state for a user+module from module_states table."""
    try:
        db = get_supabase()
        result = (
            await q(db.table("module_states")
            .select("*")
            .eq("user_id", user_id)
            .eq("module", module))
        )
        if result.data:
            return result.data[0]
    except Exception as e:
        logger.error(f"[StateEngine] Failed to get module state: {e}")

    # Return a safe default if no state record exists yet
    return {
        "user_id": user_id,
        "module": module,
        "state": {},
        "cumulative_reward": 0.0,
        "decision_count": 0,
    }


async def get_recent_events(user_id: str, module: str, limit: int = 20) -> list[dict]:
    """Fetch the most recent events for LLM context building."""
    try:
        db = get_supabase()
        result = (
            await q(db.table("events")
            .select("module, event_type, payload, source, created_at")
            .eq("user_id", user_id)
            .eq("module", module)
            .order("created_at", desc=True)
            .limit(limit))
        )
        return result.data or []
    except Exception as e:
        logger.error(f"[StateEngine] Failed to get recent events: {e}")
        return []


async def get_reward_history(user_id: str, module: str, limit: int = 20) -> list[dict]:
    """Fetch recent reward records for LLM context."""
    try:
        db = get_supabase()
        result = (
            await q(db.table("rewards")
            .select("module, event_type, reward_value, reward_source, created_at")
            .eq("user_id", user_id)
            .eq("module", module)
            .order("created_at", desc=True)
            .limit(limit))
        )
        return result.data or []
    except Exception as e:
        logger.error(f"[StateEngine] Failed to get reward history: {e}")
        return []


async def get_all_module_states(user_id: str) -> list[dict]:
    """Fetch states for all modules — used on the NeuralOrbit overview."""
    try:
        db = get_supabase()
        result = (
            await q(db.table("module_states")
            .select("*")
            .eq("user_id", user_id))
        )
        return result.data or []
    except Exception as e:
        logger.error(f"[StateEngine] Failed to get all module states: {e}")
        return []
