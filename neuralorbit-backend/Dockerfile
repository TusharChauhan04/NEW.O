FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Production-safe default: gunicorn managing uvicorn workers, no --reload.
# Local dev via docker-compose overrides this with --reload (see
# docker-compose.yml's `command:`) — this default is what actually deploys
# if the image is built and run directly, e.g. by a hosting platform.
#
# ── WHY --workers 1 (do not raise this without reading below) ───────────────
# Three components hold PER-PROCESS state and are only correct with a single
# worker. Running N workers does not scale them, it duplicates them:
#   1. app/core/scheduler.py       — APScheduler starts per process, so the
#                                    hourly decision scan would run N times an
#                                    hour, multiplying LLM cost and writing
#                                    duplicate decisions.
#   2. app/api/v1/integrations.py  — _oauth_state_store is an in-memory dict.
#                                    The OAuth callback would hit a different
#                                    worker than the one that issued the state
#                                    token ~(N-1)/N of the time, failing with
#                                    "Session Expired".
#   3. app/core/rate_limit.py      — per-process buckets mean the effective
#                                    limit becomes N× the configured value.
#
# To scale beyond one worker, all three must move to shared state (Redis is
# already provisioned in docker-compose.yml) and the scheduler must be gated
# behind a leader lock or split into its own single-instance process.
#
# --timeout / --graceful-timeout ensure a hung worker is recycled rather than
# wedging the service; --max-requests recycles workers to bound memory growth.
CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", "--workers", "1", \
     "--timeout", "60", "--graceful-timeout", "30", \
     "--max-requests", "1000", "--max-requests-jitter", "100"]
