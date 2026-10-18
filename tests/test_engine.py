from app.guardrail.engine import run_query


def test_normal_query_is_allowed_and_returns_rows():
    r = run_query("SELECT name, city FROM customers LIMIT 5")
    assert r.decision == "ALLOW"
    assert len(r.rows) == 5


def test_cartesian_product_is_blocked():
    r = run_query("SELECT c.name, oi.quantity FROM customers c, order_items oi LIMIT 10")
    assert r.decision == "BLOCK"


def test_sensitive_table_is_blocked():
    r = run_query("SELECT salary FROM employees")
    assert r.decision == "BLOCK"
