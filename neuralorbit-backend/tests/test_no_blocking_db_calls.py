"""
Architectural lock (P1): no blocking Supabase call may sit in an async context.

supabase-py is synchronous — every .execute() is a blocking HTTP round-trip.
The Dockerfile deliberately runs `--workers 1` (the scheduler, OAuth state
store, and rate limiter are all per-process), so ONE bare .execute() inside an
`async def` parks the only event loop for the full duration of the request and
becomes the throughput ceiling for the entire service.

This test walks the real AST rather than grepping, so it cannot be fooled by
comments, docstrings, or string literals mentioning .execute().
"""

import ast
import pathlib

APP = pathlib.Path(__file__).resolve().parents[1] / "app"

# Sync helpers that legitimately do DB work because every caller already hands
# them to a worker thread via asyncio.to_thread. Add to this list ONLY with a
# verified to_thread call site.
ALLOWED_SYNC_DB_FUNCTIONS = {
    "_fetch_accuracy",   # learning_engine.py — callers use asyncio.to_thread
}


def _enclosing_functions(tree):
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    def enclosing(node):
        cur = parents.get(node)
        while cur is not None:
            if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return cur
            cur = parents.get(cur)
        return None

    return enclosing


def _execute_calls(tree):
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "execute"
                and not node.args):
            yield node


def test_no_bare_execute_inside_async_function():
    offenders = []
    for path in sorted(APP.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        enclosing = _enclosing_functions(tree)
        for node in _execute_calls(tree):
            fn = enclosing(node)
            if isinstance(fn, ast.AsyncFunctionDef):
                offenders.append(
                    f"{path.relative_to(APP)}:{node.lineno} in async def {fn.name}()"
                )

    assert not offenders, (
        "Blocking DB calls inside async functions (use `await q(builder)` from "
        "app.database instead of `builder.execute()`):\n  " + "\n  ".join(offenders)
    )


def test_sync_db_helpers_are_explicitly_allowlisted():
    """
    A sync helper that touches the DB is only safe if its callers offload it.
    Catching new ones here forces that decision to be made deliberately.
    """
    found = set()
    for path in sorted(APP.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        enclosing = _enclosing_functions(tree)
        for node in _execute_calls(tree):
            fn = enclosing(node)
            if isinstance(fn, ast.FunctionDef):   # sync def
                found.add(fn.name)

    unexpected = found - ALLOWED_SYNC_DB_FUNCTIONS
    assert not unexpected, (
        f"New sync functions performing DB work: {sorted(unexpected)}. "
        "Either make them `async def` and use `await q(...)`, or confirm every "
        "caller wraps them in asyncio.to_thread and add them to "
        "ALLOWED_SYNC_DB_FUNCTIONS."
    )


def test_q_helper_actually_offloads():
    """The whole lock is meaningless if q() runs inline."""
    import inspect
    from app import database
    src = inspect.getsource(database.q)
    assert "to_thread" in src, "database.q no longer offloads to a worker thread"
