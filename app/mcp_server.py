"""MCP server: lets any AI assistant (Claude Desktop, Claude Code, Cursor, ...) use the
database safely. Both tools go through the full guardrail; nothing reaches PostgreSQL directly.

Run:   python -m app.mcp_server            (stdio transport, started by the assistant)
Role:  set GUARDRAIL_ROLE=analyst to act as a specific database role (default: the login role).
"""
import os
from typing import Optional

from mcp.server.mcpserver import MCPServer

from app.guardrail import schema_loader
from app.guardrail.audit import log_event
from app.guardrail.engine import GuardrailResponse, run_query
from app.guardrail.llm import schema_text
from app.guardrail.pipeline import ask

mcp = MCPServer("sql-guardrail")


def _role() -> Optional[str]:
    role = os.getenv("GUARDRAIL_ROLE") or None
    if role and role not in schema_loader.assumable_roles():
        raise ValueError(f"Role {role} is not permitted for the guardrail login")
    return role


def _as_dict(resp: GuardrailResponse) -> dict:
    return {
        "decision": resp.decision,            # ALLOW, REVIEW or BLOCK
        "risk_score": resp.score,
        "reasons": resp.reasons,
        "sql": resp.sql,
        "columns": resp.columns,
        "rows": [list(r) for r in resp.rows[:200]],
        "row_count": len(resp.rows),
    }


@mcp.tool()
def run_sql(sql: str) -> dict:
    """Run one read-only SQL SELECT through the guardrail. The query is validated, cost-checked
    and risk-scored first; it only executes if the decision is ALLOW."""
    resp = run_query(sql, role=_role())
    log_event("mcp_sql", None, resp)
    return _as_dict(resp)


@mcp.tool()
def ask_database(question: str) -> dict:
    """Answer a plain-English question about the database. A local model writes the SQL, the
    guardrail checks it (and repairs fixable mistakes), and the rows are returned."""
    result = ask(question, role=_role())
    log_event("mcp_question", question, result.final, result.repairs_used, result.trail)
    out = _as_dict(result.final)
    out["repairs_used"] = result.repairs_used
    return out


@mcp.tool()
def describe_schema() -> str:
    """List the tables and columns the current database role is allowed to read."""
    return schema_text(schema_loader.get_snapshot(_role()))


if __name__ == "__main__":
    mcp.run()
