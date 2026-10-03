"""
database.py — Supabase client (singleton)
Uses the service role key so it can bypass RLS for backend operations.
"""

from supabase import create_client, Client
from app.config import settings
import logging

logger = logging.getLogger(__name__)

_client: Client | None = None


async def q(builder):
    """
    Run a Supabase query builder off the event loop.

    WHY THIS EXISTS
    supabase-py is a SYNCHRONOUS client: every `.execute()` is a blocking HTTP
    round-trip. Called bare inside an `async def` handler it parks the event
    loop thread for the full duration of the request to Supabase.

    That is the throughput ceiling for the whole service, because the Dockerfile
    deliberately runs `--workers 1` (the scheduler, the OAuth state store, and
    the rate limiter are all per-process — see the Dockerfile comment). One
    event loop, serialized on DB latency, means roughly one DB-bound request at
    a time regardless of instance size.

    Wrapping in asyncio.to_thread hands the blocking call to FastAPI's default
    40-thread pool, so requests overlap instead of queueing.

    USAGE — note there is no .execute() on the builder:
        rows = (await q(db.table("events").select("*").eq("user_id", uid))).data

    The pattern was already established for one query in
    core/intelligence/learning_engine.py; this generalises it.
    """
    import asyncio
    return await asyncio.to_thread(builder.execute)


def get_supabase() -> Client:
    """Return the Supabase client (lazy-initialized singleton)."""
    global _client
    if _client is None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env"
            )
        _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
        logger.info("[NeuralOrbit] Supabase client initialized ✓")
    return _client
