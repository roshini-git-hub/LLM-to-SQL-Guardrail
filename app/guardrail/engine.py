import time
from dataclasses import dataclass, field
from typing import Any, List, Optional

from app.guardrail import policy
from app.guardrail.cost import estimate_cost
from app.guardrail.db import get_connection
from app.guardrail.risk import assess
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


def run_query(sql: str, execute: bool = True) -> GuardrailResponse:
    # Layer 1: AST validation and policy
    validation = validate(sql)
    if validation.blocked:
        risk = assess(validation, None)
        return GuardrailResponse(sql, risk.decision, risk.score, risk.reasons)

    # Layer 2: cost estimation (EXPLAIN only, nothing is executed)
    try:
        cost = estimate_cost(sql)
    except Exception as e:
        reason = "Planner rejected the query: " + str(e).splitlines()[0]
        return GuardrailResponse(sql, "BLOCK", 100, [reason])

    # Layer 3: risk decision
    risk = assess(validation, cost)
    if risk.decision != "ALLOW" or not execute:
        return GuardrailResponse(sql, risk.decision, risk.score, risk.reasons)

    # Layer 4: safe execution with row limit (role also enforces timeout and read-only)
    guarded = f"SELECT * FROM ({sql.strip().rstrip(';')}) AS guarded LIMIT {policy.MAX_LIMIT}"
    conn = get_connection()
    try:
        cur = conn.cursor()
        start = time.perf_counter()
        cur.execute(guarded)
        rows = cur.fetchall()
        elapsed = (time.perf_counter() - start) * 1000
        columns = [d[0] for d in cur.description]
    except Exception as e:
        return GuardrailResponse(sql, "BLOCK", risk.score,
                                 risk.reasons + ["Execution failed: " + str(e).splitlines()[0]])
    finally:
        conn.rollback()
        conn.close()

    return GuardrailResponse(sql, "ALLOW", risk.score, risk.reasons, columns, rows, elapsed)
