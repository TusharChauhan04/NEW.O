"""
Tests for the liveness/readiness split and production hardening of /health.

Before this, /health returned "ok" without touching the database — so a load
balancer would route traffic to an instance that could not reach Supabase —
and it leaked env/auth posture to anonymous callers.
"""

from app.config import settings


def test_health_is_liveness_only_and_does_not_touch_db(client, monkeypatch):
    """Liveness must not depend on the DB, or a DB blip restarts every pod."""
    import app.database
    def _boom():
        raise RuntimeError("db down")
    monkeypatch.setattr(app.database, "get_supabase", _boom)

    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health_exposes_config_in_dev(client, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "development")
    body = client.get("/health").json()
    # The admin Analytics page renders these; keep the contract in dev.
    assert "env" in body and "llm_provider" in body and "auth_required" in body


def test_health_hides_config_in_production(client, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    body = client.get("/health").json()
    assert body["status"] == "ok"
    for leaky in ("env", "llm_provider", "auth_required"):
        assert leaky not in body, f"/health leaked {leaky} in production"


def test_readiness_reports_ready_when_db_reachable(client, supa):
    r = client.get("/health/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"
    assert r.json()["checks"]["database"] == "ok"


def test_readiness_returns_503_when_db_unreachable(client, monkeypatch):
    import app.database
    def _boom():
        raise RuntimeError("supabase unreachable")
    monkeypatch.setattr(app.database, "get_supabase", _boom)

    r = client.get("/health/ready")
    assert r.status_code == 503, "an unreachable DB must take the instance out of rotation"
    assert r.json()["status"] == "not_ready"


def test_readiness_does_not_leak_error_details(client, monkeypatch):
    """Driver errors can carry connection strings — they must not be returned."""
    import app.database
    def _boom():
        raise RuntimeError("postgres://user:SECRET_PW@db.internal:5432")
    monkeypatch.setattr(app.database, "get_supabase", _boom)

    r = client.get("/health/ready")
    assert "SECRET_PW" not in r.text
    assert "postgres://" not in r.text
