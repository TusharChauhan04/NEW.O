from fastapi import APIRouter
from app.api.v1 import (
    events, decisions, rewards, recommendations,
    states, integrations, tracking, analytics,
    profile, admin_autonomy, admin_scheduler, admin_integrations,
    admin_intelligence, user_autonomy,
)

api_router = APIRouter()

api_router.include_router(events.router,              prefix="/events",                  tags=["Events"])
api_router.include_router(decisions.router,           prefix="/decisions",               tags=["Decisions"])
api_router.include_router(rewards.router,             prefix="/rewards",                 tags=["Rewards"])
api_router.include_router(recommendations.router,     prefix="/recommend",               tags=["AI Recommendations"])
api_router.include_router(states.router,              prefix="/states",                  tags=["Module States"])
api_router.include_router(integrations.router,        prefix="/integrations",            tags=["Integrations"])
api_router.include_router(tracking.router,            prefix="/track",                   tags=["Website Tracker (L4)"])
api_router.include_router(analytics.router,           prefix="/analytics",               tags=["Analytics"])
api_router.include_router(profile.router,             prefix="/profile",                 tags=["User Profile"])
api_router.include_router(admin_autonomy.router,      prefix="/admin/autonomy",          tags=["Admin — Autonomy"])
api_router.include_router(admin_scheduler.router,     prefix="/admin/scheduler",         tags=["Admin — Scheduler"])
api_router.include_router(admin_integrations.router,  prefix="/admin/integrations",      tags=["Admin — Integrations"])
api_router.include_router(admin_intelligence.router,  prefix="/admin/intelligence",      tags=["Admin — AI Intelligence"])
api_router.include_router(user_autonomy.router,       prefix="/user",                    tags=["User — Self Autonomy"])

