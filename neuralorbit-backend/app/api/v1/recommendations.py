"""
api/v1/recommendations.py — AI Recommendation Endpoint

POST /recommend — Sends module + question → gets AI recommendation
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Any
from app.auth.dependencies import get_current_user
from app.core.llm.recommender import generate_recommendation
from app.core.rate_limit import check_rate_limit
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class RecommendRequest(BaseModel):
    module: str
    question: str
    context: dict[str, Any] | None = None  # Optional extra context from frontend


@router.post("")
async def get_recommendation(
    req: RecommendRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Get an AI recommendation for any module.

    Example:
        POST /api/v1/recommend
        {
          "module": "crm",
          "question": "Which leads should I prioritize today?"
        }

    Returns structured recommendation with reasoning, confidence,
    and alternatives. Decision is auto-stored in the decisions table.
    """
    user_id = current_user["sub"]

    # Each call can trigger a billed LLM API request — cap per user.
    check_rate_limit(f"recommend:{user_id}", max_calls=10, window_seconds=60)

    result = await generate_recommendation(
        user_id=user_id,
        module=req.module,
        question=req.question,
        extra_context=req.context,
    )

    return {"status": "ok", "result": result}
