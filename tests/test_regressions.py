import pytest
from app.guardrail.validator import validate


@pytest.mark.parametrize("sql", [
    "SELECT name FROM products WHERE category = 'Toys' AND name <> 'drop' LIMIT 10",
    "SELECT name FROM customers WHERE city = 'Delhi' OR city = 'Mumbai' LIMIT 10",
    "SELECT date_trunc('month', order_date), count(*) FROM orders GROUP BY 1",
    "SELECT order_id FROM orders WHERE order_date >= date_trunc('month', now()) LIMIT 5",
    "SELECT name, CASE WHEN price > 500 THEN 'high' ELSE 'low' END AS tier FROM products LIMIT 50",
    "SELECT cast(total_amount AS int) FROM orders LIMIT 10",
    "SELECT row_number() OVER (ORDER BY total_amount DESC) AS rn, order_id FROM orders LIMIT 10",
])
def test_known_false_positives_stay_fixed(sql):
    assert not validate(sql).blocked


@pytest.mark.parametrize("sql", [
    "SELECT CASE WHEN true THEN pg_sleep(10) END",
    "SELECT cast(pg_sleep(1) AS text)",
    "SELECT name FROM customers WHERE city = 'x' AND pg_sleep(5) IS NOT NULL",
])
def test_dangerous_functions_hidden_in_syntax_are_still_blocked(sql):
    assert validate(sql).blocked
