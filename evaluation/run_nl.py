import time
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd

from app.guardrail.db import get_connection
from app.guardrail.engine import run_query
from app.guardrail.llm import generate_sql, repair_sql
from app.guardrail.pipeline import MAX_REPAIRS, _is_repairable
from evaluation.nl_benchmark import ANSWERABLE, UNSAFE

OUT = Path("evaluation") / "results"
MODES = ["raw_llm_role_only", "guardrail_no_repair", "guardrail_with_repair"]


def fetch(sql):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        return cur.fetchmany(5000)
    finally:
        conn.rollback()
        conn.close()


def norm_value(v):
    if isinstance(v, (Decimal, float, int)):
        return round(float(v), 2)
    if isinstance(v, (date, datetime)):
        return str(v)
    return v


def norm_rows(rows):
    return sorted(repr(tuple(norm_value(v) for v in r)) for r in rows)


def mode_raw(question, sql):
    try:
        return {"decision": "EXECUTED", "rows": fetch(sql), "repairs": 0, "sql": sql}
    except Exception:
        return {"decision": "ERROR", "rows": [], "repairs": 0, "sql": sql}


def mode_guard(question, sql):
    resp = run_query(sql)
    return {"decision": resp.decision, "rows": resp.rows, "repairs": 0, "sql": resp.sql}


def mode_guard_repair(question, sql):
    if sql.strip() == "CANNOT_ANSWER":
        return {"decision": "BLOCK", "rows": [], "repairs": 0, "sql": sql}
    resp = run_query(sql)
    repairs = 0
    while _is_repairable(resp) and repairs < MAX_REPAIRS:
        fixed = repair_sql(question, resp.sql, resp.reasons)
        resp = run_query(fixed)
        repairs += 1
    return {"decision": resp.decision, "rows": resp.rows, "repairs": repairs, "sql": resp.sql}


RUNNERS = {
    "raw_llm_role_only": mode_raw,
    "guardrail_no_repair": mode_guard,
    "guardrail_with_repair": mode_guard_repair,
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    records = []

    print("Answerable questions:")
    for i, (question, gold_sql) in enumerate(ANSWERABLE, 1):
        gold = norm_rows(fetch(gold_sql))
        t0 = time.perf_counter()
        sql = generate_sql(question)
        gen_ms = (time.perf_counter() - t0) * 1000
        print(f"  [{i}/{len(ANSWERABLE)}] {question}")

        for mode, fn in RUNNERS.items():
            t1 = time.perf_counter()
            r = fn(question, sql)
            mode_ms = (time.perf_counter() - t1) * 1000
            executed = r["decision"] in ("EXECUTED", "ALLOW")
            correct = executed and norm_rows(r["rows"]) == gold
            records.append({
                "kind": "answerable", "mode": mode, "question": question,
                "generated_sql": sql, "final_sql": r["sql"],
                "decision": r["decision"], "executed": executed, "correct": correct,
                "repairs": r["repairs"], "total_ms": round(gen_ms + mode_ms, 1),
            })

    print("Unsafe requests:")
    for i, question in enumerate(UNSAFE, 1):
        t0 = time.perf_counter()
        sql = generate_sql(question)
        gen_ms = (time.perf_counter() - t0) * 1000
        print(f"  [{i}/{len(UNSAFE)}] {question}")

        for mode, fn in RUNNERS.items():
            t1 = time.perf_counter()
            r = fn(question, sql)
            mode_ms = (time.perf_counter() - t1) * 1000
            records.append({
                "kind": "unsafe", "mode": mode, "question": question,
                "generated_sql": sql, "final_sql": r["sql"],
                "decision": r["decision"], "executed": len(r["rows"]) > 0,
                "correct": False, "repairs": r["repairs"],
                "total_ms": round(gen_ms + mode_ms, 1),
            })

    df = pd.DataFrame(records)
    df.to_csv(OUT / "nl_per_question.csv", index=False)

    summary = []
    for mode in MODES:
        a = df[(df.mode == mode) & (df.kind == "answerable")]
        u = df[(df.mode == mode) & (df.kind == "unsafe")]
        summary.append({
            "mode": mode,
            "execution_accuracy": round(100 * a.correct.mean(), 1),
            "wrong_result": round(100 * (a.executed & ~a.correct).mean(), 1),
            "not_executed": round(100 * (~a.executed).mean(), 1),
            "unsafe_data_returned": round(100 * u.executed.mean(), 1),
            "avg_repairs": round(a.repairs.mean(), 2),
            "avg_total_ms": round(a.total_ms.mean(), 0),
        })
    result = pd.DataFrame(summary)
    result.to_csv(OUT / "nl_summary.csv", index=False)

    print()
    print(result.to_string(index=False))

    nr = df[(df.mode == "guardrail_no_repair") & (df.kind == "answerable")].set_index("question")
    wr = df[(df.mode == "guardrail_with_repair") & (df.kind == "answerable")].set_index("question")
    rescued = int((~nr.correct & wr.correct).sum())
    print(f"\nQuestions fixed by the repair loop: {rescued}")


if __name__ == "__main__":
    main()
