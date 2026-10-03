"""
models/event.py — Event Pydantic schemas
"""

from pydantic import BaseModel
from typing import Any
from datetime import datetime


class EventCreate(BaseModel):
    module: str          # 'crm' | 'marketing' | 'shield' | 'website' | 'neural-orbit'
    event_type: str      # 'lead_reply' | 'meeting_booked' | 'threat_blocked' | ...
    payload: dict[str, Any] | None = None   # Flexible event-specific data
    context: dict[str, Any] | None = None   # Environmental state at event time
    source: str = "api"  # 'manual' | 'n8n' | 'api' | 'system'


class EventResponse(BaseModel):
    id: str
    user_id: str | None
    module: str
    event_type: str
    payload: dict[str, Any] | None
    context: dict[str, Any] | None
    source: str
    created_at: datetime
    reward_value: float | None = None  # Auto-calculated reward, if applicable
