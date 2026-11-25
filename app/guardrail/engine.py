import time
from dataclasses import dataclass, field
from typing import Any, List, Optional

import sqlglot
from sqlglot import exp

from app.guardrail import policy
from app.guardrail.cost import estimate_cost
from app.guardrail.db import connection
from app.guardrail.risk import assess
from app.guardrail.schema_loader import get_snapshot
from app.guardrail.validator import validate


@dataclass
class GuardrailResponse:
    sql: str
    decision: str
    score: int
    reasons: List[str]
    columns: List[str] = field(default_factory=list)
    rows: List[Any] = field(default_factory=list)
    elapsed_ms: Optional[float] = None
    role: Optional[str] = None


def apply_row_limit(sql: str, max_limit: int = policy.MAX_LIMIT) -> str:
    """Return the query with a LIMIT of at most max_limit, edited through the SQLGlot AST.

    - no LIMIT                      -> add LIMIT max_limit
    - LIMIT n with n <= max_limit   -> keep the query's own limit
    - LIMIT n with n > max_limit    -> lower it to max_limit
    - LIMIT ALL / FETCH FIRST / any non-numeric limit -> replace with max_limit
    The query itself is never wrapped in a subquery, so duplicate column names still work.
    """
    tree = sqlglot.parse_one(sql, read="postgres")
    limit = tree.args.get("limit")
    value = limit.expression if isinstance(limit, exp.Limit) else None
    if isinstance(value, exp.Literal) and value.is_int and int(value.this) <= max_limit:
        return tree.sql(dialect="postgres")
    tree.set("limit", None)
    return tree.limit(max_limit, copy=False).sql(dialect="postgres")


def run_query(sql: str, execute: bool = True, role: Optional[str] = None) -> GuardrailResponse:
    """Run one SQL string through all guardrail layers, as `role` (None = the login role)."""
    snapshot = get_snapshot(role)

    # Layer 1: AST validation against the role's live schema snapshot
    validation = validate(sql, snapshot)
    if validation.blocked:
        risk = assess(validation, None)
        return GuardrailResponse(sql, risk.decision, risk.score, risk.reasons, role=role)

    # Layer 2: cost estimation (EXPLAIN only, nothing is executed)
    try:
        cost = estimate_cost(sql, snapshot, role)
    except Exception as e:
        reason = "Planner rejected the query: " + str(e).splitlines()[0]
        return GuardrailResponse(sql, "BLOCK", 100, [reason], role=role)

    # Layer 3: risk decision (cost thresholds are relative to this database's size)
    risk = assess(validation, cost, snapshot)
    if risk.decision != "ALLOW" or not execute:
        return GuardrailResponse(sql, risk.decision, risk.score, risk.reasons, role=role)

    # Layer 4: safe execution with row limit (connection is read-only with a statement timeout)
    try:
        guarded = apply_row_limit(sql)
    except Exception as e:
        return GuardrailResponse(sql, "BLOCK", risk.score, risk.reasons +
                                 ["Could not apply row limit: " + str(e).splitlines()[0]], role=role)

    try:
        with connection(role) as conn:
            cur = conn.cursor()
            start = time.perf_counter()
            cur.execute(guarded)
            rows = cur.fetchall()
            elapsed = (time.perf_counter() - start) * 1000
            columns = [d[0] for d in cur.description]
    except Exception as e:
        return GuardrailResponse(sql, "BLOCK", risk.score, risk.reasons +
                                 ["Execution failed: " + str(e).splitlines()[0]], role=role)

    return GuardrailResponse(sql, "ALLOW", risk.score, risk.reasons, columns, rows, elapsed, role)
