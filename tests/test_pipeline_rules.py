from app.guardrail.engine import GuardrailResponse
from app.guardrail.pipeline import _is_repairable


def _resp(reason, decision="BLOCK"):
    return GuardrailResponse("x", decision, 100, [reason])


def test_security_violations_are_never_repaired():
    for rule in (
        "blocked_table", "sensitive_column", "forbidden_statement",
        "multiple_statements", "hidden_write", "forbidden_function", "unknown_table",
        "star_on_restricted_table", "row_locking", "select_into", "recursive_cte",
    ):
        assert not _is_repairable(_resp(f"[{rule}] example"))


def test_fixable_problems_are_repairable():
    assert _is_repairable(_resp('Planner rejected the query: column "x" does not exist'))
    assert _is_repairable(_resp("[syntax_error] could not parse"))
    assert _is_repairable(_resp("[missing_limit] no limit", decision="REVIEW"))
