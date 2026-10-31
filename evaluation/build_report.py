from collections import Counter
from pathlib import Path

import pandas as pd

from evaluation.dataset import DATASET
from evaluation.final_set import FINAL
from evaluation.holdout import HOLDOUT

R = Path("evaluation") / "results"
OUT = Path("docs")
OUT.mkdir(exist_ok=True)

NAMES = {
    "baseline": "Approach",
    "detection_rate": "Detection %",
    "malicious_detected": "Malicious detected %",
    "expensive_detected": "Expensive detected %",
    "false_positive_rate": "False positives %",
    "precision": "Precision %",
    "avg_latency_ms": "Avg latency (ms)",
    "p95_latency_ms": "p95 latency (ms)",
}


def load(name, required=False):
    p = R / name
    if not p.exists():
        if required:
            raise SystemExit(f"Missing {p}. Run the evaluation first.")
        return None
    return pd.read_csv(p)


def table(df):
    if df is None:
        return "_Results file not found._\n"
    df = df.rename(columns=NAMES)
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in df.iterrows():
        out.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(out) + "\n"


def row(df, name):
    return df[df["baseline"] == name].iloc[0]


def sizes(ds):
    c = Counter(label for _, label in ds)
    return len(ds), c["safe"], c["malicious"], c["expensive"]


dev = load("summary.csv", True)
hold_before = load("holdout_before_fix.csv", True)
hold_after = load("holdout_summary.csv")
final = load("final_summary_frozen.csv", True)
postfix = load("final_summary_postfix.csv")
nl = load("nl_summary.csv")
nl_before = load("nl_summary_before_hints.csv")

d, h, f = sizes(DATASET), sizes(HOLDOUT), sizes(FINAL)
fg, fa = row(final, "full_guardrail"), row(final, "ast_only")
fr, fb = row(final, "db_role_only"), row(final, "regex_blacklist")
hg, dg = row(hold_before, "full_guardrail"), row(dev, "full_guardrail")

nl_text = "_Natural-language benchmark results not found. Run `python -m evaluation.run_nl`._\n"
if nl is not None:
    nl_text = table(nl)
    if nl_before is not None:
        nl_text += "\nBefore adding value hints to the prompt:\n\n" + table(nl_before)

postfix_text = ""
if postfix is not None:
    postfix_text = (
        "\n**After post-evaluation fixes (not independent).** The same queries were re-run after "
        "the fixes listed in Section 7. Because the fixes were made after seeing these queries, "
        "this table shows that the fixes work and caused no regression; it is not a measure of "
        "generalization.\n\n" + table(postfix)
    )

stress_path = OUT / "repair_stress_section.md"
stress_text = stress_path.read_text(encoding="utf-8") if stress_path.exists() else ""

report = f"""# Risk-Aware LLM-to-SQL Guardrail for Secure and Cost-Efficient Database Query Execution

TODO: team members, course, institution, date.

## Abstract

Large language models can translate questions into SQL, but the generated queries may contain
errors, access data the user is not entitled to, or place heavy load on the database. This
project builds a guardrail that sits between an LLM and a PostgreSQL database. It parses each
query into an abstract syntax tree (SQLGlot), checks it against schema and column policies,
estimates its cost from the query plan (EXPLAIN without execution), and combines these signals
into a risk score that allows, flags or blocks the query. Fixable problems are sent back to the
LLM for repair; security violations never are. Execution uses a restricted read-only database
role with a timeout and a row limit. On a final test set of {f[0]} queries written after the
rules were frozen, the full guardrail detected {fg.detection_rate}% of unsafe queries with a
{fg.false_positive_rate}% false-positive rate, compared with {fa.detection_rate}% for AST rules
alone, {fr.detection_rate}% for the database role alone and {fb.detection_rate}% for a keyword
blacklist.

## 1. Introduction

Natural-language interfaces to databases are attractive because they remove the need to write
SQL. The risk is that the SQL is produced by a model that can be wrong, can be manipulated by
the user (prompt injection), and has no sense of cost. Three problems follow:

1. **Correctness:** syntax errors, wrong columns or wrong joins.
2. **Security:** reading protected tables or columns, running destructive or administrative
   statements, or calling dangerous functions.
3. **Performance:** queries such as unconstrained cross joins or recursive queries that can
   consume the database's resources.

Database permissions alone address only part of this: a read-only role cannot stop a query from
being expensive, and cannot explain why a query was refused. This project adds a layer that
examines each query before it runs.

## 2. Related approaches

TODO: add citations. Suggested topics: (a) text-to-SQL systems and benchmarks (for example
Spider and BIRD), (b) SQL injection detection and prevention, (c) database access control
(role-based access, column privileges, row-level security), (d) query optimizer cost models,
(e) keyword blacklists as a common but weak defense.

## 3. System design

The architecture diagram is in `README.md`. A query passes through these layers in order:

1. **LLM generation** with a prompt that lists only the tables and columns the role may use,
   plus the exact stored values of categorical columns.
2. **AST validation and policy** (SQLGlot): exactly one statement, SELECT only, no hidden writes,
   row locking, SELECT INTO or recursive queries, allowlisted tables and functions, no
   restricted columns, and no star expansion over tables with hidden columns.
3. **Cost estimation:** `EXPLAIN (FORMAT JSON)` without ANALYZE, so the query is never run.
   The plan tree is examined for large sequential scans, joins without conditions and very
   large row estimates, using the maximum cost over all plan nodes rather than only the root,
   because a LIMIT can make the root look cheap.
4. **Risk score and decision:** any blocking rule gives BLOCK immediately; otherwise warnings and
   cost points are summed to ALLOW, REVIEW or BLOCK using fixed thresholds.
5. **Repair loop:** problems that can be fixed (syntax, unknown column, high cost, missing LIMIT)
   are sent back to the LLM, at most twice. Security violations are never repaired, so that a
   manipulated model cannot probe the policy by retrying.
6. **Safe execution:** a restricted read-only role with a 5-second statement timeout, an outer
   row limit, and a rolled-back transaction.
7. **Audit log:** every request, decision, score and reason is recorded and shown on the dashboard.

## 4. Implementation

Python 3.12, PostgreSQL 16, SQLGlot, FastAPI, Streamlit (dark theme), and a local model served
by Ollama (temperature 0 for repeatability). TODO: state the model name and size you used and the
hardware. The test database has customers, products, orders (200,000 rows), order items
(600,000 rows) and an employees table that the role must never read. The restricted role is also
denied the email and phone columns of customers.

## 5. Experimental setup

**Query sets.** Three sets of labeled SQL were used, plus a natural-language benchmark:

| Set | Purpose | Total | Safe | Malicious | Expensive |
|---|---|---|---|---|---|
| Development | used while building the rules | {d[0]} | {d[1]} | {d[2]} | {d[3]} |
| Held-out | written after the rules; evasion attempts | {h[0]} | {h[1]} | {h[2]} | {h[3]} |
| Final | written last; run once with rules frozen (git tag `final-eval-frozen`) | {f[0]} | {f[1]} | {f[2]} | {f[3]} |

TODO: state how the queries were written and what tools or assistance were used, according to
your course's rules.

**Approaches compared.** (1) no guardrail (reference, detects nothing by definition),
(2) a regex keyword blacklist, (3) the restricted database role alone, (4) AST validation and
policy rules alone, (5) the full guardrail.

**Metrics.** Detection rate (share of malicious and expensive queries stopped), false-positive
rate (share of safe queries wrongly stopped), precision, and latency. For the full guardrail,
"stopped" means a decision other than ALLOW. Latency for the guardrail covers validation and
EXPLAIN only, not execution, so it measures what the layer adds.

## 6. Results

### 6.1 Development set (used for tuning)

{table(dev)}
![Development set](figures/development_detection.png)

### 6.2 Held-out set (first run, before any tuning on it)

The full guardrail reached {hg.detection_rate}% detection and {hg.false_positive_rate}% false
positives on this set.

{table(hold_before)}
![Held-out set](figures/held_out_detection.png)

After the fixes described in Section 7 the same set gave:

{table(hold_after)}
This second run is not independent of the fixes.

### 6.3 Final set (rules frozen)

{table(final)}
![Final set](figures/final_detection.png)

![Latency](figures/final_latency.png)

The full guardrail added about {fg.avg_latency_ms} ms per query on average, whereas the database
role alone averaged {fr.avg_latency_ms} ms, because it lets slow queries run until the timeout.
{postfix_text}
### 6.4 Which layer caught what (final set, frozen rules)

| Layer | Malicious caught | Expensive caught |
|---|---|---|
| AST and policy rules | 27 | 2 |
| PostgreSQL planner (permissions) | 3 | 0 |
| Cost and plan analysis | 0 | 3 |
| Not caught | 0 | 1 |

The three malicious queries caught only by PostgreSQL were `SELECT *` over a table with hidden
columns (two queries) and `SELECT ... FOR UPDATE`. The guardrail's own rules did not cover them;
the database role did. The two expensive queries caught by the AST layer were most likely blocked
incidentally because `generate_series` was not on the function allowlist, so only the three
caught by cost analysis count as genuine cost detection. The one missed expensive query was an
unbounded recursive query. This query was tested directly, wrapped in an outer LIMIT 1000 as the engine wrapped allowed queries, and run as the restricted role. The form that selects rows returned its 1,000 rows in under a tenth of a second, because PostgreSQL evaluates recursive queries lazily and the LIMIT stopped it. The form that counts rows ran until the 5-second statement timeout and was cancelled after 5.07 s. So the frozen guardrail did not detect the query beforehand; it was bounded only by the execution timeout, and only the row-selecting form was bounded by the row limit. A rule blocking recursive queries was added after the final evaluation (the current decision for this query is BLOCK), so that change is not measured on an independent set.

### 6.5 Natural-language benchmark

Plain-English questions with a known correct result, run through three setups: the LLM's SQL
sent straight to the database, the guardrail without repair, and the guardrail with up to two
repairs. Execution accuracy compares the returned rows with those of a reference query.

{nl_text}
Reading this table: in this run the model made no mistake that the guardrail could detect, so the three setups scored the same and the repair loop did not fire. The benchmark therefore shows that the guardrail did not reduce correctness; it does not show a benefit, which the SQL sets and the repair stress test measure. The questions were also used to decide on the value-hint fix, so they are not an independent test. Time per question is almost entirely model generation; differences of a few tens of milliseconds between setups are within noise.

The unsafe requests in this benchmark were mostly refused by the model itself (it was only told
about permitted tables), so that test measures the prompt rather than the guardrail. The guardrail
is measured by the SQL sets above.

{stress_text}
## 7. Error analysis: what the evaluation found

Each problem below was found by the evaluation, fixed, and turned into a regression test.

1. **AND/OR treated as functions.** SQLGlot represents AND and OR as function nodes, so every query
   with two conditions was blocked. Found by the development set.
2. **CASE, CAST and window functions treated as forbidden functions.** The same cause. Found by the
   held-out set. The fix excludes syntax constructs but still checks any real function inside them;
   tests confirm a dangerous function hidden inside CASE or CAST is still blocked.
3. **Function names differ between SQL text and the parser** (for example `date_trunc` appears as
   `timestamp_trunc`, `string_agg` as `group_concat`).
4. **A conservative allowlist blocks harmless functions** (`nullif`, `trim`, `concat`), a deliberate
   trade-off: unknown functions are blocked by default.
5. **Star expansion.** `SELECT *` over a table with hidden columns was only warned about; the database
   role stopped it. Added a rule using the policy's list of tables with hidden columns.
6. **Row locking and SELECT INTO** were not checked. Added.
7. **Unbounded recursive queries** scored as low risk. Added a rule blocking recursive queries for this role.
8. **Wrong categorical value spelling in generated SQL** (the model wrote `'Cancelled'` where the data holds
   `'cancelled'`), giving a valid query and a wrong answer that no safety layer can detect. Fixed by
   adding the exact stored values of categorical columns to the prompt.

Items 5 to 7 were fixed after the final evaluation and are therefore not measured on an independent set.

## 8. Limitations

- The query sets are small, written by hand, and run on one small schema; results will not transfer
  unchanged to a large production database.
- The development and held-out sets were used to make fixes, so they overestimate performance on
  new queries. Only the final set was run once on frozen rules, and fixes were made after it.
- Cost detection relies on the planner's estimates, which can be wrong when statistics are stale.
- The function allowlist is conservative and produces false positives for functions it does not know.
- Column restrictions are checked by name; the guardrail does not trace columns through arbitrarily
  complex subqueries and views, and relies on the database role as a second layer.
- Aggregate queries can still leak information about individuals (for example a COUNT with a very
  narrow filter); this is not addressed.
- The benchmark's model refusals reflect the prompt, not the guardrail.
- Only one local model was tried and its SQL quality limits query correctness.

## 9. Future work

A learned cost model trained on real execution times, column-level lineage through subqueries,
PostgreSQL row-level security, per-role policies and thresholds, minimum group sizes for
aggregates to limit inference, and a larger, independently written test set.

## 10. Conclusion

Layering AST validation, policy rules and plan-based cost estimation on top of a restricted
database role stopped more unsafe queries than any simpler approach on every set tested, and caught
expensive queries that rule-based and permission-based approaches miss, at a cost of about
{fg.avg_latency_ms} ms per query. The evaluation also exposed real weaknesses, which were fixed
and recorded. The result is a working prototype with measured behavior rather than a claim of
perfect protection.

## Appendix: reproducing the results

See `README.md`. Evaluation commands: `python -m evaluation.run_eval`, `run_holdout`, `run_final`,
`run_nl`, then `python -m evaluation.make_figures` and `python -m evaluation.build_report`.
"""

extra = ""
for name in ("repair_stress_section.md", "cost_model_section.md"):
    sec = OUT / name
    if sec.exists():
        body = sec.read_text(encoding="utf-8").strip()
        if body.splitlines()[0] not in report:
            extra += body + "\n\n"
marker = "## 7. Error analysis: what the evaluation found"
if extra and marker in report:
    report = report.replace(marker, extra + marker, 1)

(OUT / "REPORT.md").write_text(report, encoding="utf-8")
print("Wrote", OUT / "REPORT.md")



