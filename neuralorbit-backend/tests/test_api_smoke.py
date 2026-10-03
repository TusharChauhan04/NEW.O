"""Smoke tests — verify the app boots and the fake-DB fixture wires up."""

from tests.conftest import DEV_USER_ID


def test_health_endpoint_responds(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["app"] == "neuralorbit-backend"


def test_fake_supabase_is_installed_widely(supa):
    # Sanity: the sys.modules sweep should reach many modules, not just one.
    assert supa._patched_module_count >= 10


def test_fake_supabase_applies_eq_filters(supa):
    """
    The ownership/RBAC fixes are implemented as .eq() filters, so the fake must
    actually filter — otherwise those tests would pass vacuously.
    """
    supa.seed("integrations", [
        {"id": "a", "user_id": DEV_USER_ID, "module": "website"},
        {"id": "b", "user_id": "someone-else", "module": "website"},
    ])
    db = supa.table("integrations")
    rows = db.select("*").eq("user_id", DEV_USER_ID).execute().data
    assert len(rows) == 1
    assert rows[0]["id"] == "a"


def test_fake_supabase_insert_persists(supa):
    supa.table("events").insert({"module": "crm", "event_type": "x"}).execute()
    rows = supa.table("events").select("*").execute().data
    assert len(rows) == 1
    assert rows[0]["module"] == "crm"
    assert "id" in rows[0]
