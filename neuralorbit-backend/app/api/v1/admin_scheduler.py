"""
api/v1/admin_scheduler.py — Admin Scheduler Control Endpoints

GET  /admin/scheduler/status    — Last run summary, next run time, history
POST /admin/scheduler/trigger   — Manually trigger the decision scan right now

ADDITIVE: Only reads from scheduler.py state dict and fires existing function.
          No existing endpoint, DB table, or code is modified.
"""

from fastapi import APIRouter, Depends, HTTPException
from app.auth.dependencies import get_admin_user
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# Holds references to fire-and-forget background tasks so asyncio can't
# garbage-collect them mid-execution (a bare asyncio.create_task() result
# that isn't stored anywhere is eligible for GC as soon as the enclosing
# scope returns — see https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task).
_background_tasks: set = set()


# ── GET /admin/scheduler/status ───────────────────────────────────────────────

@router.get("/status")
async def get_scheduler_status(current_user: dict = Depends(get_admin_user)):
    """
    Returns the current status of the background decision scanner.
    Reads from the in-memory summary stored in scheduler.py.
    """
    try:
        from app.core.scheduler import get_scheduler_summary, get_scheduler_instance
        summary  = get_scheduler_summary()
        instance = get_scheduler_instance()

        is_running = bool(instance and instance.running)
        next_run   = None

        if is_running:
            try:
                job = instance.get_job("decision_scan")
                if job and job.next_run_time:
                    next_run = job.next_run_time.isoformat()
            except Exception:
                pass

        return {
            "is_running":    is_running,
            "next_run":      next_run,
            "last_run":      summary.get("last_run"),
            "last_result":   summary.get("last_result"),
            "run_history":   summary.get("run_history", []),
            "total_runs":    summary.get("total_runs", 0),
        }

    except Exception as e:
        logger.error(f"[AdminScheduler] Status error: {e}")
        return {
            "is_running":   False,
            "next_run":     None,
            "last_run":     None,
            "last_result":  None,
            "run_history":  [],
            "total_runs":   0,
            "error":        str(e),
        }


# ── POST /admin/scheduler/trigger ─────────────────────────────────────────────

@router.post("/trigger")
async def trigger_manual_scan(current_user: dict = Depends(get_admin_user)):
    """
    Manually trigger the AI decision generator scan right now.
    Useful for testing or forcing a scan before the next hourly job.
    Runs async — returns immediately with a job_started confirmation.
    """
    admin_id = current_user["sub"]
    logger.info(f"[AdminScheduler] Manual scan triggered by admin={admin_id[:8]}")

    try:
        import asyncio
        from app.core.intelligence.decision_generator import run_decision_generator
        from app.core.scheduler import record_run

        async def _run():
            try:
                result = await run_decision_generator()
                record_run(result, triggered_by="admin")
                logger.info(
                    f"[AdminScheduler] Manual scan complete — "
                    f"users={result.get('users_scanned', 0)} "
                    f"decisions={result.get('decisions_generated', 0)}"
                )
            except Exception as e:
                logger.error(f"[AdminScheduler] Manual scan error: {e}")

        # Fire and forget — runs in background, endpoint returns immediately.
        # Keep a strong reference until it finishes so it can't be GC'd mid-run.
        task = asyncio.create_task(_run())
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

        return {
            "status":     "started",
            "message":    "Manual AI scan triggered. Check /status in 5–10 seconds for results.",
            "triggered_by": admin_id[:8],
        }

    except Exception as e:
        logger.error(f"[AdminScheduler] Trigger failed: {e}")
        raise HTTPException(status_code=500, detail=f"Could not trigger scan: {e}")
