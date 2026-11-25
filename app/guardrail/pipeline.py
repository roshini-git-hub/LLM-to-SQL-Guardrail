from dataclasses import dataclass
from typing import List, Optional

from app.guardrail.engine import GuardrailResponse, run_query
from app.guardrail.llm import generate_sql, repair_sql
from app.guardrail.schema_loader import get_snapshot

MAX_REPAIRS = 2

# Violations that must never be "repaired" by asking the LLM again
SECURITY_RULES = (
    "blocked_table", "sensitive_column", "forbidden_statement",
    "multiple_statements", "hidden_write", "forbidden_function", "unknown_table",
    "star_on_restricted_table", "row_locking", "select_into", "recursive_cte",
)


@dataclass
class AskResult:
    question: str
    final: GuardrailResponse
    attempts: List[GuardrailResponse]
    repairs_used: int


def _is_repairable(resp: GuardrailResponse) -> bool:
    if resp.decision == "ALLOW":
        return False
    for reason in resp.reasons:
        for rule in SECURITY_RULES:
            if reason.startswith(f"[{rule}]"):
                return False
    return True


def ask(question: str, role: Optional[str] = None, model: Optional[str] = None) -> AskResult:
    snapshot = get_snapshot(role)
    sql = generate_sql(question, snapshot, model)

    if sql.strip() == "CANNOT_ANSWER":
        refusal = GuardrailResponse(
            sql, "BLOCK", 100,
            ["The question cannot be answered within the allowed schema"], role=role,
        )
        return AskResult(question, refusal, [refusal], 0)

    attempts = []
    resp = run_query(sql, role=role)
    attempts.append(resp)

    repairs = 0
    while _is_repairable(resp) and repairs < MAX_REPAIRS:
        sql = repair_sql(question, resp.sql, resp.reasons, snapshot, model)
        resp = run_query(sql, role=role)
        attempts.append(resp)
        repairs += 1

    return AskResult(question, resp, attempts, repairs)
