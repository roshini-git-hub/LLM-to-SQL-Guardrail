from pathlib import Path

import pandas as pd

from app.guardrail.schema_loader import get_snapshot
from app.guardrail.engine import run_query
from app.guardrail.llm import MODEL, _get_client, repair_sql
from app.guardrail.llm import extract_sql as _extract_sql
from app.guardrail.pipeline import MAX_REPAIRS, _is_repairable
from evaluation.nl_benchmark import ANSWERABLE
from evaluation.run_nl import fetch, norm_rows

OUT = Path("evaluation") / "results"
DOCS = Path("docs")

# Degraded first attempt: table names only, no columns
WEAK_PROMPT = (
    "You translate questions into PostgreSQL SELECT queries. "
    "The database has these tables: " + ", ".join(t.name for t in get_snapshot().accessible_tables()) + ". "
    "Output exactly one SQL query and nothing else. "
    "If the question cannot be answered, output exactly: CANNOT_ANSWER"
)


def weak_generate(question):
    resp = _get_client().chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": WEAK_PROMPT},
            {"role": "user", "content": f"Question: {question}"},
        ],
        options={"temperature": 0, "num_predict": 800},
    )
    return _extract_sql(resp["message"]["content"])


def is_correct(resp, gold):
    return resp.decision == "ALLOW" and norm_rows(resp.rows) == gold


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(exist_ok=True)
    records = []

    for i, (question, gold_sql) in enumerate(ANSWERABLE, 1):
        print(f"[{i}/{len(ANSWERABLE)}] {question}")
        gold = norm_rows(fetch(gold_sql))
        sql = weak_generate(question)

        if sql.strip() == "CANNOT_ANSWER":
            records.append({"question": question, "first_sql": sql, "first_decision": "REFUSED",
                            "first_reasons": "", "final_sql": sql, "final_decision": "REFUSED",
                            "repairs": 0, "correct_first": False, "correct_final": False})
            continue

        first = run_query(sql)
        resp, repairs = first, 0
        while _is_repairable(resp) and repairs < MAX_REPAIRS:
            fixed = repair_sql(question, resp.sql, resp.reasons, get_snapshot())
            resp = run_query(fixed)
            repairs += 1

        records.append({
            "question": question,
            "first_sql": sql,
            "first_decision": first.decision,
            "first_reasons": " | ".join(first.reasons),
            "final_sql": resp.sql,
            "final_decision": resp.decision,
            "repairs": repairs,
            "correct_first": is_correct(first, gold),
            "correct_final": is_correct(resp, gold),
        })

    df = pd.DataFrame(records)
    df.to_csv(OUT / "nl_repair_stress.csv", index=False)

    n = len(df)
    first_acc = round(100 * df.correct_first.mean(), 1)
    final_acc = round(100 * df.correct_final.mean(), 1)
    rescued = int((~df.correct_first & df.correct_final).sum())
    needed = int((df.first_decision.isin(["BLOCK", "REVIEW"])).sum())
    still_wrong = int((~df.correct_final).sum())

    summary = pd.DataFrame([{
        "questions": n,
        "first_attempt_correct_pct": first_acc,
        "after_repair_correct_pct": final_acc,
        "rejected_on_first_attempt": needed,
        "rescued_by_repair": rescued,
        "still_wrong_after_repair": still_wrong,
    }])
    summary.to_csv(OUT / "nl_repair_stress_summary.csv", index=False)

    print()
    print(summary.to_string(index=False))

    print("\n=== Rescued by the repair loop ===")
    for r in df[~df.correct_first & df.correct_final].itertuples():
        print(f"\n{r.question}")
        print(f"  first : {r.first_sql}")
        print(f"  reason: {r.first_reasons}")
        print(f"  fixed : {r.final_sql}  (repairs: {r.repairs})")

    print("\n=== Still wrong after repair ===")
    for r in df[~df.correct_final].itertuples():
        print(f"\n{r.question}")
        print(f"  decision: {r.first_decision} -> {r.final_decision}")
        print(f"  final : {r.final_sql}")

    snippet = f"""### 6.6 Repair-loop stress test

With the full prompt the model rarely made correctable mistakes (a spot check of eight further
questions needed no repair at all), so the repair loop was also tested under a deliberately degraded
condition. For these {n} questions the model's first attempt was given only the table names, not the
columns, so wrong column names were likely. Repairs then received the rejected query and the
reasons it was rejected, together with the full schema prompt.

| Questions | Correct on first attempt | Correct after repair | Rejected on first attempt | Rescued by repair | Still wrong |
|---|---|---|---|---|---|
| {n} | {first_acc}% | {final_acc}% | {needed} | {rescued} | {still_wrong} |

Only problems the guardrail can detect are repaired (for example a column that does not exist). A
query that is valid but answers the wrong question is allowed through unchanged, so the repair
loop cannot improve those. This is a stress test under degraded conditions, not the system's normal operating mode.
"""
    (DOCS / "repair_stress_section.md").write_text(snippet, encoding="utf-8")
    print("\nWrote docs\\repair_stress_section.md")


if __name__ == "__main__":
    main()
