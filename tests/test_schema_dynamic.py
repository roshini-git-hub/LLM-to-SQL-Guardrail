"""The guardrail learns permissions from the database. Changing a GRANT, COMMENT or RLS policy
changes its behaviour with no code change."""
import time

from app.guardrail import schema_loader
from app.guardrail.engine import run_query
from app.guardrail.schema_loader import load_snapshot, looks_sensitive


def test_snapshot_lists_only_columns_the_role_can_read():
    analyst = load_snapshot("analyst")
    support = load_snapshot("support")
    assert analyst.role == "analyst"
    assert [c.name for c in analyst.table("customers").hidden_columns] == ["email", "phone"]
    assert analyst.table("employees").accessible is False
    assert support.table("customers").column("email").can_select
    assert support.table("products").accessible is False
    assert not support.table("orders").column("total_amount").can_select


def test_foreign_keys_rls_and_sizes_are_read_from_catalogs():
    snap = load_snapshot("analyst")
    joins = {fk.describe() for fk in snap.usable_foreign_keys()}
    assert "orders.customer_id = customers.customer_id" in joins
    assert snap.table("orders").rls_enabled
    assert snap.table("orders").rows > 100_000
    assert {p.name for p in load_snapshot("city_manager").policies} == {"one_city"}


def test_sensitive_columns_from_comments_and_names():
    assert looks_sensitive("email", None)
    assert looks_sensitive("contact", "PII: home address")
    assert looks_sensitive("emp_salary", None)
    assert not looks_sensitive("company", None)  # 'pan' token heuristic must not match
    assert load_snapshot("support").table("customers").column("phone").sensitive


def test_same_query_different_role_different_decision():
    sql = "SELECT name, email FROM customers LIMIT 5"
    assert run_query(sql, role="analyst").decision == "BLOCK"       # no GRANT on email
    assert run_query(sql, role="support").decision == "REVIEW"      # granted, but PII
    assert run_query("SELECT name FROM products LIMIT 5", role="support").decision == "BLOCK"


def test_row_level_security_limits_rows_per_role():
    sql = "SELECT city, count(*) FROM customers GROUP BY city"
    analyst = run_query(sql, role="analyst")
    manager = run_query(sql, role="city_manager")
    assert len(analyst.rows) == 5
    assert [r[0] for r in manager.rows] == ["Hyderabad"]
    # orders are filtered through the customers policy as well
    total = run_query("SELECT count(*) FROM orders", role="analyst").rows[0][0]
    mine = run_query("SELECT count(*) FROM orders", role="city_manager").rows[0][0]
    assert 0 < mine < total


def test_revoking_a_grant_blocks_without_code_change(admin):
    sql = "SELECT category, count(*) FROM products GROUP BY category"
    schema_loader.invalidate_all()
    assert run_query(sql, role="analyst").decision == "ALLOW"
    try:
        admin.execute("REVOKE SELECT ON products FROM analyst")
        schema_loader.invalidate_all()  # the listener does this automatically in the API
        r = run_query(sql, role="analyst")
        assert r.decision == "BLOCK" and "[blocked_table]" in r.reasons[0]
    finally:
        admin.execute("GRANT SELECT ON products TO analyst")
        schema_loader.invalidate_all()
    assert run_query(sql, role="analyst").decision == "ALLOW"


def test_event_trigger_notifies_listener(admin):
    schema_loader.start_listener()
    try:
        time.sleep(1.5)  # let the listener connect
        before = schema_loader.notification_count()
        schema_loader.get_snapshot("analyst")
        admin.execute("COMMENT ON COLUMN products.price IS 'list price'")
        deadline = time.time() + 5
        while schema_loader.notification_count() == before and time.time() < deadline:
            time.sleep(0.1)
        assert schema_loader.notification_count() > before
        assert "analyst" not in schema_loader._cache  # cache was cleared
    finally:
        admin.execute("COMMENT ON COLUMN products.price IS NULL")
        schema_loader.stop_listener()


def test_api_rejects_roles_the_guardrail_cannot_assume():
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        assert client.post("/query", json={"sql": "SELECT 1", "role": "postgres"}).status_code == 403
        r = client.post("/query", json={"sql": "SELECT name FROM products LIMIT 1"},
                        headers={"X-DB-Role": "analyst"})
        assert r.status_code == 200 and r.json()["decision"] == "ALLOW"
        assert "email" not in client.get("/schema", params={"role": "analyst"}).json()["tables"]["customers"]["columns"]
