from pathlib import Path

p = Path("evaluation/build_report.py")
t = p.read_text(encoding="utf-8")

OLD = "TODO: add your measurement from Step 67 (how it behaved at execution)."
NEW = (
    "This query was tested directly, wrapped in an outer LIMIT 1000 as the engine wrapped allowed "
    "queries, and run as the restricted role. The form that selects rows returned its 1,000 rows in under "
    "a tenth of a second, because PostgreSQL evaluates recursive queries lazily and the LIMIT stopped it. "
    "The form that counts rows ran until the 5-second statement timeout and was cancelled after 5.07 s. "
    "So the frozen guardrail did not detect the query beforehand; it was bounded only by the execution "
    "timeout, and only the row-selecting form was bounded by the row limit. A rule blocking recursive queries "
    "was added after the final evaluation (the current decision for this query is BLOCK), so that change "
    "is not measured on an independent set."
)

if OLD in t:
    p.write_text(t.replace(OLD, NEW), encoding="utf-8")
    print("patched")
elif "tested directly, wrapped in an outer LIMIT" in t:
    print("already patched")
else:
    print("text not found - paste the line containing 'unbounded recursive query' from evaluation/build_report.py")
