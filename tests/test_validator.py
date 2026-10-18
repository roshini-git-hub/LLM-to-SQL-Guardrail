import pytest
from app.guardrail.validator import validate


@pytest.mark.parametrize("sql", [
    "SELECT name, city FROM customers LIMIT 10",
    "SELECT count(*) FROM orders",
    "SELECT status, sum(total_amount) FROM orders GROUP BY status",
    "SELECT c.name, o.total_amount FROM customers c JOIN orders o "
    "ON c.customer_id = o.customer_id LIMIT 20",
])
def test_legit_queries_pass(sql):
    assert not validate(sql).blocked


@pytest.mark.parametrize("sql,rule", [
    ("DROP TABLE orders", "forbidden_statement"),
    ("DELETE FROM orders", "forbidden_statement"),
    ("SELECT * FROM orders; DROP TABLE orders", "multiple_statements"),
    ("SELECT salary FROM employees", "blocked_table"),
    ("SELECT email FROM customers LIMIT 5", "sensitive_column"),
    ("SELECT pg_sleep(10)", "forbidden_function"),
    ("SELECT * FROM pg_catalog.pg_user", "unknown_table"),
    ("SELEC name FROM customers", "syntax_error"),
])
def test_attacks_blocked(sql, rule):
    result = validate(sql)
    assert result.blocked
    assert rule in {f.rule for f in result.findings}
