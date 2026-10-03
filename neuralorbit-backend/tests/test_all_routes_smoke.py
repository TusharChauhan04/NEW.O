"""
Broad runtime smoke: every parameterless GET route must not 500.

Unit tests cover specific behaviours; this covers BREADTH. The P1 refactor
rewrote 88 call sites across 20 files from `builder.execute()` to
`await q(builder)`, and most of those endpoints have no dedicated test. A
compile check cannot catch an await applied to the wrong expression — only
actually calling the route can.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


def _parameterless_get_routes():
    return sorted({
        r.path for r in app.routes
        if getattr(r, "methods", None) and "GET" in r.methods and "{" not in r.path
    })


@pytest.mark.parametrize("path", _parameterless_get_routes())
def test_get_route_does_not_500(path, client, supa):
    r = client.get(path)
    assert r.status_code < 500, f"{path} -> {r.status_code}: {r.text[:300]}"


def test_smoke_actually_covers_the_api(client, supa):
    """Guard against the parametrisation silently collapsing to nothing."""
    api_routes = [p for p in _parameterless_get_routes() if p.startswith("/api/")]
    assert len(api_routes) >= 15, f"only {len(api_routes)} API routes discovered"
