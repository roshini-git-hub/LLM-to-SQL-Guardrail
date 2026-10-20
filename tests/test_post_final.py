import pytest
from app.guardrail.validator import validate


@pytest.mark.parametrize("sql", [
    "SELECT nullif(city, 'Delhi') FROM customers LIMIT 10",
    "SELECT trim(name) FROM products LIMIT 10",
    "SELECT concat(name, ' - ', category) FROM products LIMIT 10",
    "SELECT string_agg(DISTINCT category, ', ') FROM products",
])
def test_harmless_functions_allowed(sql):
    assert not validate(sql).blocked


def test_recursive_cte_blocked():
    sql = "WITH RECURSIVE x AS (SELECT 1 AS n UNION ALL SELECT n + 1 FROM x) SELECT * FROM x"
    assert validate(sql).blocked


def test_dangerous_function_still_blocked_next_to_allowed_ones():
    assert validate("SELECT trim(pg_read_file('/etc/passwd'))").blocked
