"""
conftest.py — Shared test fixtures for the integration/API test layer.

WHY THIS EXISTS
---------------
The unit tests (test_auth_dependencies, test_prompts, test_rate_limit,
test_config, test_executor) call functions directly. They never exercise a
route through FastAPI, so they can't catch a regression in routing, dependency
wiring, request validation, or the ownership/RBAC filters that several security
fixes depend on.

This file provides an in-memory stand-in for the Supabase client so the real
HTTP routes can be exercised end to end without a live database.

IMPORTANT — the fake DOES apply .eq() filters. That is deliberate: several
fixes (the tracker-snippet IDOR fix, admin-vs-own-rows scoping) are implemented
*as* .eq() filters. A mock that ignored them would make those tests pass
vacuously while the real bug went undetected.

Nothing here is imported by app/ — this is test-only scaffolding and cannot
affect the running application.
"""

import sys
import pytest
from fastapi.testclient import TestClient


# ── Fake Supabase ─────────────────────────────────────────────────────────

class FakeResult:
    """Mimics the Supabase client's response object (`.data`)."""

    def __init__(self, data):
        self.data = data
        self.count = len(data) if isinstance(data, list) else None


class FakeQuery:
    """
    Chainable stand-in for Supabase's query builder.

    Supports the subset of the API this codebase actually uses. Unsupported
    chain methods are no-ops that return self, so a new .order()/.range() call
    in app code won't break these tests — only .eq() filtering is emulated,
    because that's what the security fixes rely on.
    """

    def __init__(self, store, table_name):
        self._store = store                  # live reference, so inserts persist
        self._table = table_name
        self._filters = []
        self._op = "select"
        self._payload = None

    # -- operations --
    def select(self, *_a, **_k):
        self._op = "select"
        return self

    def insert(self, payload, *_a, **_k):
        self._op = "insert"
        self._payload = payload if isinstance(payload, list) else [payload]
        return self

    def upsert(self, payload, *_a, **_k):
        self._op = "insert"
        self._payload = payload if isinstance(payload, list) else [payload]
        return self

    def update(self, payload, *_a, **_k):
        self._op = "update"
        self._payload = payload
        return self

    def delete(self, *_a, **_k):
        self._op = "delete"
        return self

    # -- filters (only eq is emulated; see module docstring) --
    def eq(self, column, value):
        self._filters.append((column, value))
        return self

    def neq(self, *_a, **_k): return self
    def gt(self, *_a, **_k): return self
    def gte(self, *_a, **_k): return self
    def lt(self, *_a, **_k): return self
    def lte(self, *_a, **_k): return self
    def in_(self, *_a, **_k): return self
    def is_(self, *_a, **_k): return self
    def like(self, *_a, **_k): return self
    def ilike(self, *_a, **_k): return self
    def order(self, *_a, **_k): return self
    def limit(self, *_a, **_k): return self
    def range(self, *_a, **_k): return self
    def single(self, *_a, **_k):
        # PostgREST .single() returns ONE OBJECT, not a list, and errors unless
        # exactly one row matches. Modelling it as a no-op returning self made
        # result.data a list, so callers doing `result.data.get(...)` blew up
        # here but worked in production — the fake was hiding, not finding, bugs.
        self._single = True
        return self

    def maybe_single(self, *_a, **_k):
        # Same shape as single(), but 0 rows yields None instead of erroring.
        self._single = True
        self._single_optional = True
        return self

    @staticmethod
    def _read_column(row, column):
        """
        Resolve a column reference, including PostgREST's JSONB text accessor
        `col->>key` (used by decision_generator's trigger-based dedup).
        """
        if "->>" in column:
            base, _, key = column.partition("->>")
            container = row.get(base.strip())
            if isinstance(container, dict):
                return container.get(key.strip())
            return None
        return row.get(column)

    def _matching(self):
        rows = self._store
        for column, value in self._filters:
            rows = [r for r in rows if str(self._read_column(r, column)) == str(value)]
        return rows

    def _shape(self, rows):
        """Apply PostgREST .single()/.maybe_single() result semantics."""
        if not getattr(self, "_single", False):
            return FakeResult(rows)
        if len(rows) == 1:
            return FakeResult(rows[0])
        if getattr(self, "_single_optional", False) and not rows:
            return FakeResult(None)
        raise Exception(
            f"PGRST116: .single() expected exactly 1 row, got {len(rows)}"
        )

    def execute(self):
        if self._op == "insert":
            inserted = []
            for item in self._payload:
                row = dict(item)
                row.setdefault("id", f"fake-id-{len(self._store) + len(inserted) + 1}")
                row.setdefault("created_at", "2026-01-01T00:00:00+00:00")
                inserted.append(row)
            self._store.extend(inserted)
            return FakeResult(inserted)

        if self._op == "update":
            matched = self._matching()
            for row in matched:
                row.update(self._payload)
            return FakeResult(matched)

        if self._op == "delete":
            matched = self._matching()
            for row in matched:
                self._store.remove(row)
            return FakeResult(matched)

        return self._shape(list(self._matching()))


class FakeSupabase:
    """Stand-in for the Supabase Client. `.table(name)` returns a FakeQuery."""

    def __init__(self, tables=None):
        self.tables = {name: list(rows) for name, rows in (tables or {}).items()}

    def table(self, name):
        self.tables.setdefault(name, [])
        return FakeQuery(self.tables[name], name)

    # Some admin code paths touch auth.admin.list_users(); keep it harmless.
    @property
    def auth(self):
        return self

    @property
    def admin(self):
        return self

    def list_users(self, *_a, **_k):
        return []

    def seed(self, table, rows):
        """Replace a table's contents. Returns self for chaining."""
        self.tables[table] = list(rows)
        return self


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def supa(monkeypatch):
    """
    Installs a FakeSupabase across every app module that holds a reference to
    get_supabase.

    Routers do `from app.database import get_supabase` at module scope, so
    patching app.database alone would not reach them. Sweeping sys.modules
    catches every already-imported holder, and covers new modules added later
    without this fixture needing an update.
    """
    import app.main  # noqa: F401  — ensures the whole app tree is imported

    fake = FakeSupabase()

    def _get_fake():
        return fake

    patched = 0
    for name, module in list(sys.modules.items()):
        if name.startswith("app.") and hasattr(module, "get_supabase"):
            monkeypatch.setattr(module, "get_supabase", _get_fake, raising=False)
            patched += 1

    assert patched > 0, "FakeSupabase was not installed anywhere — check import paths"
    fake._patched_module_count = patched
    return fake


@pytest.fixture
def client():
    """
    TestClient WITHOUT the context-manager form, so the app's lifespan does not
    run — this deliberately avoids starting the real APScheduler background job
    during tests.
    """
    from app.main import app
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """
    The rate limiter keeps process-global state. Without this, one test's
    requests would count against another's and cause order-dependent failures.
    """
    from app.core import rate_limit
    rate_limit._buckets.clear()
    yield
    rate_limit._buckets.clear()


@pytest.fixture(autouse=True)
def _dev_auth_by_default(monkeypatch):
    """
    Default every test to the dev-bypass auth path (AUTH_REQUIRED=False), which
    is this project's documented local-dev default. Tests that need real JWT
    verification override it explicitly.
    """
    from app.config import settings
    monkeypatch.setattr(settings, "AUTH_REQUIRED", False)


DEV_USER_ID = "00000000-0000-0000-0000-000000000001"
