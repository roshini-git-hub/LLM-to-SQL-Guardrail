from dataclasses import dataclass
from typing import List

from app.guardrail.engine import GuardrailResponse, run_query
from app.guardrail.llm import generate_sql, repair_sql

MAX_REPAIRS = 2

# Violations that must never be "repaired" by asking the LLM again
SECURITY_RULES = (
    "blocked_table", "sensitive_column", "forbidden_statement",
    "multiple_statements", "hidden_write", "forbidden_function", "unknown_table",
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


def ask(question: str) -> AskResult:
    sql = generate_sql(question)

    if sql.strip() == "CANNOT_ANSWER":
        refusal = GuardrailResponse(
            sql, "BLOCK", 100,
            ["The question cannot be answered within the allowed schema"],
        )
        return AskResult(question, refusal, [refusal], 0)

    attempts = []
    resp = run_query(sql)
    attempts.append(resp)

    repairs = 0
    while _is_repairable(resp) and repairs < MAX_REPAIRS:
        sql = repair_sql(question, resp.sql, resp.reasons)
        resp = run_query(sql)
        attempts.append(resp)
        repairs += 1

    return AskResult(question, resp, attempts, repairs)
