import asyncio

from app import mcp_server


def test_mcp_exposes_guarded_tools():
    names = {t.name for t in asyncio.run(mcp_server.mcp.list_tools())}
    assert {"ask_database", "run_sql", "describe_schema"} <= names


def test_run_sql_goes_through_the_guardrail(monkeypatch):
    monkeypatch.setattr(mcp_server, "log_event", lambda *a, **k: None)
    monkeypatch.setenv("GUARDRAIL_ROLE", "analyst")
    ok = mcp_server.run_sql("SELECT name FROM products LIMIT 2")
    assert ok["decision"] == "ALLOW" and ok["row_count"] == 2
    assert mcp_server.run_sql("SELECT email FROM customers LIMIT 2")["decision"] == "BLOCK"
    assert mcp_server.run_sql("DELETE FROM orders")["decision"] == "BLOCK"
    assert "email" not in mcp_server.describe_schema()
