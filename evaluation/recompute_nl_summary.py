from pathlib import Path

import pandas as pd

R = Path("evaluation") / "results"
MODES = ["raw_llm_role_only", "guardrail_no_repair", "guardrail_with_repair"]

for src, dst in [("nl_per_question.csv", "nl_summary.csv"),
                 ("nl_per_question_before_hints.csv", "nl_summary_before_hints.csv")]:
    p = R / src
    if not p.exists():
        print(f"\n{src} not found, skipped")
        continue
    df = pd.read_csv(p)
    for c in ("executed", "correct"):
        df[c] = df[c].astype(str).str.lower().eq("true")
    rows = []
    for m in MODES:
        a = df[(df["mode"] == m) & (df["kind"] == "answerable")]
        u = df[(df["mode"] == m) & (df["kind"] == "unsafe")]
        rows.append({
            "mode": m,
            "execution_accuracy": round(100 * a["correct"].mean(), 1),
            "wrong_result": round(100 * (a["executed"] & ~a["correct"]).mean(), 1),
            "not_executed": round(100 * (~a["executed"]).mean(), 1),
            "unsafe_data_returned": round(100 * u["executed"].mean(), 1),
            "avg_repairs": round(a["repairs"].mean(), 2),
            "avg_total_ms": round(a["total_ms"].mean(), 0),
        })
    out = pd.DataFrame(rows)
    out.to_csv(R / dst, index=False)
    print(f"\n=== {dst} ===")
    print(out.to_string(index=False))
