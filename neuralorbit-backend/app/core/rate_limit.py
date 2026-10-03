"""
core/rate_limit.py — Minimal in-memory rate limiter.

No new dependency (Redis/slowapi) — this keeps parity with the rest of this
codebase's single-instance assumptions (the in-memory OAuth state store in
oauth_handler.py, and the single-instance APScheduler in scheduler.py). If
this backend is ever scaled to >1 worker/instance, this — like those — will
need to move to a shared store; Redis is already provisioned in
docker-compose.yml for exactly that future need.
"""

import time
from collections import defaultdict
from fastapi import HTTPException, status

_buckets: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(key: str, max_calls: int, window_seconds: int) -> None:
    """Raise 429 if `key` has made >= max_calls calls within window_seconds."""
    now = time.time()
    bucket = _buckets[key]
    cutoff = now - window_seconds
    while bucket and bucket[0] < cutoff:
        bucket.pop(0)
    if len(bucket) >= max_calls:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please slow down and try again shortly.",
        )
    bucket.append(now)
