from app.guardrail.engine import run_query
from app.guardrail.validator import validate
from evaluation.dataset import SAFE

for sql in SAFE:
    v = validate(sql)
    r = run_query(sql, execute=False)
    if v.blocked or r.decision != "ALLOW":
        print("=" * 80)
        print(sql)
        print("  AST :", [(f.rule, f.message) for f in v.findings])
        print("  FULL:", r.decision, r.score, r.reasons)
