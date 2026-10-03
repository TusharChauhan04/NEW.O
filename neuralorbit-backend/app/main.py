"""
app/main.py — NeuralOrbit FastAPI Application Entry Point
"""

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import settings
from app.api.v1.router import api_router
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger("neuralorbit")

# ── Fail-closed guard ───────────────────────────────────────────────────────
# Refuse to boot rather than silently serve unauthenticated admin access to
# the internet. See app/config.py::validate_production_config for the reasoning.
from app.config import validate_production_config
validate_production_config(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"[NeuralOrbit] Backend starting — env={settings.APP_ENV}")
    logger.info(f"[NeuralOrbit] Auth required: {settings.AUTH_REQUIRED}")
    logger.info(f"[NeuralOrbit] LLM provider: {settings.LLM_PROVIDER}")

    # ── Phase 4 Milestone 2: Background Scheduler (non-blocking) ──────────
    try:
        from app.core.scheduler import start_scheduler
        start_scheduler(interval_minutes=60)
    except Exception as _se:
        logger.warning(f"[NeuralOrbit] Scheduler failed to start (non-critical): {_se}")
    # ── End Scheduler ──────────────────────────────────────────────────────

    yield

    # ── Shutdown ───────────────────────────────────────────────────────────
    try:
        from app.core.scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass
    logger.info("[NeuralOrbit] Backend shutting down")


app = FastAPI(
    title="NeuralOrbit AI Backend",
    description=(
        "Intelligence Layer for the NeuralOrbit AI Operating System. "
        "Handles event tracking, reward scoring, and AI recommendations."
    ),
    version="1.0.0",
    # API docs advertise the full admin surface (every route, every schema).
    # Useful in development, an unnecessary map for an attacker in production.
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
    lifespan=lifespan,
)

# ── CORS Middleware ────────────────────────────────────────────────────────
_dev_mode = settings.APP_ENV == "development"
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _dev_mode else settings.cors_origins_list,
    allow_credentials=not _dev_mode,   # credentials+wildcard is illegal in browsers
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────
app.include_router(api_router, prefix="/api/v1")


# ── Health Checks ─────────────────────────────────────────────────────────
# Two endpoints, because they answer different questions:
#   /health       — LIVENESS. Is the process up? No I/O, always fast. This is
#                   what a restart policy should watch.
#   /health/ready — READINESS. Can this instance actually serve traffic, i.e.
#                   is the database reachable? This is what a load balancer
#                   should watch before routing requests to it.
# Previously only /health existed and it reported "ok" without touching
# Supabase, so a balancer would happily route traffic to an instance that
# could not reach its own database.

@app.get("/health", tags=["System"])
async def health_check():
    body = {
        "status": "ok",
        "app": "neuralorbit-backend",
        "version": "1.0.0",
    }
    # These describe the deployment's security posture. Fine for the local
    # admin dashboard (which renders them on the Analytics page), but not
    # something to hand to anonymous callers in production.
    if not settings.is_production:
        body.update({
            "env": settings.APP_ENV,
            "llm_provider": settings.LLM_PROVIDER,
            "auth_required": settings.AUTH_REQUIRED,
        })
    return body


@app.get("/health/ready", tags=["System"])
async def readiness_check(response: Response):
    """Returns 503 when a dependency is unavailable, so orchestrators can
    keep this instance out of rotation instead of sending it doomed traffic."""
    checks: dict[str, str] = {}
    healthy = True

    try:
        from app.database import get_supabase, q
        # Cheap round-trip: bounded by limit(1), not a table scan.
        await q(get_supabase().table("reward_config").select("id").limit(1))
        checks["database"] = "ok"
    except Exception as e:
        healthy = False
        # Log the detail, return only a generic marker — connection strings and
        # driver errors should not reach an unauthenticated caller.
        logger.error(f"[Health] Readiness DB check failed: {e}")
        checks["database"] = "unavailable"

    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {"status": "ready" if healthy else "not_ready", "checks": checks}
