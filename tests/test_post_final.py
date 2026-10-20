import pytest
from app.guardrail.validator import validate


@pytest.mark.parametrize("sql", [
    "SELECT nullif(city, 'Delhi') FROM customers LIMIT 10",
    "SELECT trim(name) FROM products LIMIT 10",
    "SELECT concat(name, ' - ', category) FROM products LIMIT 10",
    "SELECT string_agg(DISTINCT category, ', ') FROM products",
    "SELECT count(*) FROM customers",
    "SELECT * FROM orders LIMIT 5",
])
def test_legitimate_queries_allowed(sql):
    assert not validate(sql).blocked


@pytest.mark.parametrize("sql,rule", [
    ("SELECT * FROM customers LIMIT 5", "star_on_restricted_table"),
    ("SELECT c.* FROM customers c", "star_on_restricted_table"),
    ("SELECT * FROM orders FOR UPDATE", "row_locking"),
    ("WITH RECURSIVE x AS (SELECT 1 AS n UNION ALL SELECT n + 1 FROM x) SELECT * FROM x",
     "recursive_cte"),
    ("SELECT trim(pg_read_file('/etc/passwd'))", "forbidden_function"),
])
def test_gaps_found_in_final_evaluation_stay_closed(sql, rule):
    result = validate(sql)
    assert result.blocked
    assert rule in {f.rule for f in result.findings}
