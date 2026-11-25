import pytest

from app.guardrail.engine import apply_row_limit


@pytest.mark.parametrize("sql,expected", [
    ("SELECT a FROM t", "SELECT a FROM t LIMIT 1000"),
    ("SELECT a FROM t LIMIT 5", "SELECT a FROM t LIMIT 5"),
    ("SELECT a FROM t LIMIT 999999", "SELECT a FROM t LIMIT 1000"),
    ("SELECT a FROM t LIMIT ALL", "SELECT a FROM t LIMIT 1000"),
    ("SELECT a FROM t FETCH FIRST 50000 ROWS ONLY", "SELECT a FROM t LIMIT 1000"),
])
def test_limit_is_injected_or_clamped(sql, expected):
    assert apply_row_limit(sql, 1000) == expected


def test_duplicate_column_names_are_not_wrapped():
    out = apply_row_limit("SELECT c.name, p.name FROM c JOIN p ON c.id = p.id", 1000)
    assert "guarded" not in out and out.endswith("LIMIT 1000")


def test_union_gets_a_limit():
    assert apply_row_limit("SELECT a FROM t UNION SELECT a FROM u", 1000).endswith("LIMIT 1000")
