"""
models/reward.py — Reward Pydantic schemas
"""

from pydantic import BaseModel
from datetime import datetime


class ManualRewardCreate(BaseModel):
    module: str
    event_type: str
    reward_value: float
    notes: str | None = None


class RewardConfigItem(BaseModel):
    module: str
    event_type: str
    reward_value: float
    description: str | None = None
    is_active: bool = True


class RewardSummary(BaseModel):
    module: str | None
    total_reward: float
    event_count: int
    avg_reward: float
    by_module: dict
    recent: list[dict]
