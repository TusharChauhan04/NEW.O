"""
core/llm/recommender.py — Full AI Recommendation Pipeline

Flow:
1. Fetch current module state from Supabase
2. Fetch recent events + reward history (context for LLM)
3. Call LLM client (mock/openai)
4. Store the decision in the decisions table
5. Return structured recommendation to API caller
"""

from app.core.llm.client import get_llm_client
from app.core.llm.prompts import get_known_mistakes
from app.core.intelligence.state_engine import (
    get_module_state,
    get_recent_events,
    get_reward_history,
)
from app.database import get_supabase, q
import logging

logger = logging.getLogger(__name__)


async def generate_recommendation(
    user_id: str,
    module: str,
    question: str,
    extra_context: dict | None = None,
) -> dict:
    """
    Full recommendation pipeline.
    Returns the LLM result dict with an added decision_id if stored successfully.
    """

    # 1 — Gather context
    state = await get_module_state(user_id, module)
    recent_events = await get_recent_events(user_id, module, limit=12)
    reward_history = await get_reward_history(user_id, module, limit=12)
    known_mistakes = await get_known_mistakes(user_id, module)

    context = {
        "state": state,
        "recent_events": recent_events[:6],
        "reward_history": reward_history[:6],
        "cumulative_reward": state.get("cumulative_reward", 0),
        "decision_count": state.get("decision_count", 0),
        "question": question,
        "known_mistakes": known_mistakes,
        **(extra_context or {}),
    }

    # 2 — Call LLM
    client = get_llm_client()
    result = await client.recommend(module=module, context=context, question=question)

    # 3 — Store decision in DB
    try:
        db = get_supabase()
        record = await q(db.table("decisions").insert({
            "user_id":        user_id,
            "module":         module,
            "action":         result["recommendation"],
            "action_code":    result.get("action_code"),
            "reasoning":      result.get("reasoning"),
            "confidence":     result.get("confidence"),
            "state_snapshot": {
                "cumulative_reward": context["cumulative_reward"],
                "decision_count":    context["decision_count"],
                "recent_event_count": len(recent_events),
            },
            "alternatives":   result.get("alternatives", []),
            "outcome":        "pending",
        }))

        if record.data:
            result["decision_id"] = record.data[0]["id"]
            logger.info(
                f"[Recommender] Decision stored — "
                f"module={module} decision_id={result['decision_id'][:8]}"
            )
    except Exception as e:
        logger.error(f"[Recommender] Failed to store decision: {e}")

    return result
