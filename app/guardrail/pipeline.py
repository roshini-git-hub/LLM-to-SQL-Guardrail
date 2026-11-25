"""Question -> LLM -> guardrail -> (automatic repair) -> answer.

Repair order for a FIXABLE failure:
  1. dialect fix   : rewrite MySQL / SQL Server syntax to PostgreSQL with SQLGlot (no LLM call)
  2. LLM repair    : send precise, schema-aware feedback back to the LLM (at most MAX_REPAIRS)
Security violations are never repaired: they are blocked at once and the LLM is not told why.
"""
import logging
from dataclasses import dataclass, field
from typing import List, Optional

from app.guardrail.engine import GuardrailResponse, run_query
from app.guardrail.llm import generate_sql, repair_sql
from app.guardrail.repair import build_feedback, fix_dialect
from app.guardrail.schema_loader import get_snapshot

log = logging.getLogger("guardrail.pipeline")

MAX_REPAIRS = 2

# Violations that must never be "repaired" by asking the LLM again
SECURITY_RULES = (
    "blocked_table", "sensitive_column", "forbidden_statement",
    "multiple_statements", "hidden_write", "forbidden_function", "unknown_table",
    "star_on_restricted_table", "row_locking", "select_into", "recursive_cte",
    "sensitive_access",
)


@dataclass
class AskResult:
    question: str
    final: GuardrailResponse
    attempts: List[GuardrailResponse]
    repairs_used: int                       # LLM repair calls (max MAX_REPAIRS)
    dialect_fixes: int = 0                  # automatic SQLGlot rewrites (no LLM call)
    trail: List[dict] = field(default_factory=list)   # every attempt, for the audit log


def _security_rules_hit(resp: GuardrailResponse) -> set:
    hit = {rule for reason in resp.reasons for rule in SECURITY_RULES
           if reason.startswith(f"[{rule}]")}
    if any("permission denied" in r for r in resp.reasons):
        hit.add("permission_denied")        # the database itself refused: also security
    return hit


def _is_repairable(resp: GuardrailResponse) -> bool:
    return resp.decision != "ALLOW" and not _security_rules_hit(resp)


def _may_be_dialect_mistake(resp: GuardrailResponse) -> bool:
    # IFNULL / ISNULL / GETDATE look like forbidden functions but are just another dialect.
    # A rewrite is still checked by the whole guardrail, so this cannot let anything through.
    return resp.decision != "ALLOW" and _security_rules_hit(resp) <= {"forbidden_function"}


class _Run:
    """Runs queries for one question and records every attempt."""

    def __init__(self, role):
        self.role = role
        self.attempts: List[GuardrailResponse] = []
        self.trail: List[dict] = []
        self.dialect_fixes = 0

    def _record(self, source: str, resp: GuardrailResponse, feedback=None):
        self.attempts.append(resp)
        entry = {"attempt": len(self.attempts), "source": source, "sql": resp.sql,
                 "decision": resp.decision, "score": resp.score, "reasons": resp.reasons,
                 "feedback_sent": feedback}
        self.trail.append(entry)
        log.info("attempt %(attempt)s [%(source)s] %(decision)s: %(sql)s | %(reasons)s", entry)

    def run(self, sql: str, source: str, feedback=None) -> GuardrailResponse:
        resp = run_query(sql, role=self.role)
        self._record(source, resp, feedback)
        if _may_be_dialect_mistake(resp):
            for rewritten in fix_dialect(sql):
                fixed = run_query(rewritten, role=self.role)
                self._record("dialect_fix", fixed)
                if fixed.decision == "ALLOW":
                    self.dialect_fixes += 1
                    return fixed
        return resp


def ask(question: str, role: Optional[str] = None, model: Optional[str] = None) -> AskResult:
    snapshot = get_snapshot(role)
    run = _Run(role)

    def refusal():
        r = GuardrailResponse("CANNOT_ANSWER", "BLOCK", 100,
                              ["The question cannot be answered within the allowed schema"],
                              role=role)
        run._record("llm", r)
        return r

    sql = generate_sql(question, snapshot, model)
    repairs = 0
    if sql.strip() == "CANNOT_ANSWER":
        resp = refusal()
    else:
        resp = run.run(sql, "llm")
        while _is_repairable(resp) and repairs < MAX_REPAIRS:
            feedback = build_feedback(resp.sql, resp.reasons, snapshot)
            sql = repair_sql(question, resp.sql, feedback, snapshot, model)
            repairs += 1
            if sql.strip() == "CANNOT_ANSWER":
                resp = refusal()
                break
            resp = run.run(sql, "llm_repair", feedback)

    return AskResult(question, resp, run.attempts, repairs, run.dialect_fixes, run.trail)
