"""
Tests for app/core/rate_limit.py — the in-memory limiter added to close
BUG-14 (no rate limiting anywhere, incl. billed LLM calls).
"""

import pytest
from fastapi import HTTPException

from app.core import rate_limit


@pytest.fixture(autouse=True)
def _clean_buckets():
    """Each test gets an empty bucket store — avoids cross-test bleed."""
    rate_limit._buckets.clear()
    yield
    rate_limit._buckets.clear()


def test_allows_calls_under_the_limit():
    for _ in range(5):
        rate_limit.check_rate_limit("k", max_calls=5, window_seconds=60)
    # no exception raised


def test_rejects_calls_over_the_limit():
    for _ in range(5):
        rate_limit.check_rate_limit("k", max_calls=5, window_seconds=60)
    with pytest.raises(HTTPException) as exc_info:
        rate_limit.check_rate_limit("k", max_calls=5, window_seconds=60)
    assert exc_info.value.status_code == 429


def test_keys_are_independent():
    for _ in range(5):
        rate_limit.check_rate_limit("user-a", max_calls=5, window_seconds=60)
    # a different key must not be affected by user-a's usage
    rate_limit.check_rate_limit("user-b", max_calls=5, window_seconds=60)


def test_old_calls_fall_out_of_the_window(monkeypatch):
    t = [1000.0]
    monkeypatch.setattr(rate_limit.time, "time", lambda: t[0])

    for _ in range(5):
        rate_limit.check_rate_limit("k", max_calls=5, window_seconds=60)
    with pytest.raises(HTTPException):
        rate_limit.check_rate_limit("k", max_calls=5, window_seconds=60)

    # advance past the window — old calls should expire and free up room
    t[0] += 61
    rate_limit.check_rate_limit("k", max_calls=5, window_seconds=60)  # no raise
