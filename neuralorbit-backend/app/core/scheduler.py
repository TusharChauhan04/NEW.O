"""
core/scheduler.py — NeuralOrbit Background Job Scheduler

Phase 4 Milestone 2: Runs the proactive decision generator on a schedule.

Uses APScheduler (AsyncIOScheduler) — fully async, no threads, no blocking.
Registered in main.py lifespan so it starts/stops cleanly with the app.

Jobs registered:
  - decision_scan: every 60 minutes — runs run_decision_generator()

SAFE: Scheduler only reads/writes its own jobs. It never modifies any
      existing endpoint, existing function, or existing DB table.
      All errors are caught and logged without crashing the server.
"""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

# Module-level scheduler instance (shared across the app)
_scheduler: AsyncIOScheduler | None = None

# ── In-memory run summary (read by admin_scheduler.py) ──────────────────────
# Holds the last 10 run records. Reset on server restart (no DB needed).
_run_summary: dict = {
    "last_run":    None,
    "last_result": None,
    "run_history": [],   # list of {ts, users, decisions, triggered_by, duration_s}
    "total_runs":  0,
}


async def _run_decision_scan() -> None:
    """Wrapper that calls the decision generator and logs the result."""
    import time
    t0 = time.monotonic()
    try:
        from app.core.intelligence.decision_generator import run_decision_generator
        result = await run_decision_generator()
        duration = round(time.monotonic() - t0, 2)
        record_run(result, triggered_by="scheduler", duration_s=duration)
        logger.info(
            f"[Scheduler] decision_scan complete — "
            f"users={result.get('users_scanned', 0)} "
            f"generated={result.get('decisions_generated', 0)}"
        )
    except Exception as e:
        # Never let scheduler crash the whole server
        logger.error(f"[Scheduler] decision_scan job failed (non-critical): {e}")


def start_scheduler(interval_minutes: int = 60) -> AsyncIOScheduler:
    """
    Create and start the background scheduler.
    Called once from main.py lifespan on startup.

    Args:
        interval_minutes: How often to run the decision scan (default: 60 min)

    Returns the running scheduler instance.
    """
    global _scheduler

    if _scheduler and _scheduler.running:
        logger.warning("[Scheduler] Already running — skipping duplicate start")
        return _scheduler

    _scheduler = AsyncIOScheduler()

    # ── Job 1: Proactive Decision Scan ──────────────────────────────────────
    _scheduler.add_job(
        func        = _run_decision_scan,
        trigger     = IntervalTrigger(minutes=interval_minutes),
        id          = "decision_scan",
        name        = "Proactive AI Decision Generator",
        replace_existing = True,
        max_instances    = 1,   # Never run two scans at the same time
        misfire_grace_time = 300,  # OK if up to 5 min late
    )

    _scheduler.start()
    logger.info(
        f"[Scheduler] ✓ Started — "
        f"decision_scan every {interval_minutes} min"
    )
    return _scheduler


def stop_scheduler() -> None:
    """
    Cleanly shut down the scheduler.
    Called from main.py lifespan on shutdown.
    """
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[Scheduler] Stopped cleanly")


# ── Public helpers (read-only, used by admin_scheduler.py) ───────────────────

def record_run(result: dict, triggered_by: str = "scheduler", duration_s: float = 0.0) -> None:
    """
    Record a completed scan into the in-memory summary.
    Called by _run_decision_scan() and admin manual trigger.
    This function only writes to the _run_summary dict — no DB, no side effects.
    """
    from datetime import datetime, timezone
    global _run_summary

    now = datetime.now(timezone.utc).isoformat()
    entry = {
        "ts":           now,
        "users":        result.get("users_scanned", 0),
        "decisions":    result.get("decisions_generated", 0),
        "triggered_by": triggered_by,
        "duration_s":   duration_s,
    }

    _run_summary["last_run"]    = now
    _run_summary["last_result"] = entry
    _run_summary["total_runs"] += 1

    # Keep only the last 10 runs
    _run_summary["run_history"].insert(0, entry)
    _run_summary["run_history"] = _run_summary["run_history"][:10]


def get_scheduler_summary() -> dict:
    """Return the current run summary. Read-only — never mutates state."""
    return dict(_run_summary)


def get_scheduler_instance() -> AsyncIOScheduler | None:
    """Return the live scheduler instance (for next_run_time, job status)."""
    return _scheduler
