from pathlib import Path

import pandas as pd

R = Path("evaluation") / "results"
MODES = ["raw_llm_role_only", "guardrail_no_repair", "guardrail_with_repair"]


def summarize(df):
    rows = []
    for mode in MODES:
        a = df[(df["mode"] == mode) & (df["kind"] == "answerable")]
        u = df[(df["mode"] == mode) & (df["kind"] == "unsafe")]
        rows.append({
            "mode": mode,
            "execution_accuracy": round(100 * a["correct"].mean(), 1),
            "wrong_result": round(100 * (a["executed"] & ~a["correct"]).mean(), 1),
            "not_executed": round(100 * (~a["executed"]).mean(), 1),
            "unsafe_data_returned": round(100 * u["executed"].mean(), 1),
            "avg_repairs": round(a["repairs"].mean(), 2),
            "avg_total_ms": round(a["total_ms"].mean(), 0),
        })
    return pd.DataFrame(rows)


def rescued(df):
    base = df[(df["mode"] == "guardrail_no_repair") & (df["kind"] == "answerable")].set_index("question")
    rep = df[(df["mode"] == "guardrail_with_repair") & (df["kind"] == "answerable")].set_index("question")
    return int((~base["correct"] & rep["correct"]).sum())


PAIRS = [
    ("nl_per_question.csv", "nl_summary.csv", "CURRENT RUN"),
    ("nl_per_question_before_hints.csv", "nl_summary_before_hints.csv", "BEFORE VALUE HINTS"),
]

for src, dst, label in PAIRS:
    p = R / src
    if not p.exists():
        print(f"\n{label}: {src} not found, skipped")
        continue
    df = pd.read_csv(p)
    for c in ("executed", "correct"):
        df[c] = df[c].astype(bool)
    s = summarize(df)
    s.to_csv(R / dst, index=False)
    print(f"\n=== {label} ===")
    print(s.to_string(index=False))
    print(f"Questions fixed by the repair loop: {rescued(df)}")
