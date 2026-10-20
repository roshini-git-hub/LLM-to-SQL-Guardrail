from collections import Counter

from app.guardrail.engine import run_query
from app.guardrail.validator import validate
from evaluation.final_set import FINAL


def layer(sql):
    if validate(sql).blocked:
        return "1. AST and policy rules"
    resp = run_query(sql, execute=False)
    if resp.decision == "ALLOW":
        return "0. NOT CAUGHT"
    if any("Planner rejected" in r for r in resp.reasons):
        return "2. Database planner (permissions or syntax)"
    return "3. Cost and plan analysis or risk score"


counts = Counter()
by_layer = {}
for sql, label in FINAL:
    if label == "safe":
        continue
    name = layer(sql)
    counts[(label, name)] += 1
    by_layer.setdefault(name, []).append(sql)

print("\nCaught by layer:")
for (label, name), n in sorted(counts.items()):
    print(f"  {label:10s} {name:50s} {n}")

print("\nQueries caught only by the database planner:")
for sql in by_layer.get("2. Database planner (permissions or syntax)", []):
    print("  -", sql)
