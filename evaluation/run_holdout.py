from pathlib import Path

import pandas as pd

from app.guardrail.engine import run_query
from evaluation.baselines import BASELINES
from evaluation.holdout import HOLDOUT

OUT = Path("evaluation") / "results"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, fn in BASELINES.items():
        print(f"Running {name} on the held-out set ...")
        for sql, label in HOLDOUT:
            flagged, ms = fn(sql)
            rows.append({"baseline": name, "label": label, "sql": sql,
                         "flagged": bool(flagged), "ms": round(ms, 2)})

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "holdout_per_query.csv", index=False)

    summary = []
    for name, g in df.groupby("baseline", sort=False):
        safe = g[g.label == "safe"]
        malicious = g[g.label == "malicious"]
        expensive = g[g.label == "expensive"]
        unsafe = g[g.label != "safe"]
        tp = int(unsafe.flagged.sum())
        fp = int(safe.flagged.sum())
        summary.append({
            "baseline": name,
            "detection_rate": round(100 * tp / len(unsafe), 1),
            "malicious_detected": round(100 * malicious.flagged.mean(), 1),
            "expensive_detected": round(100 * expensive.flagged.mean(), 1),
            "false_positive_rate": round(100 * fp / len(safe), 1),
            "precision": round(100 * tp / (tp + fp), 1) if (tp + fp) else 0.0,
            "avg_latency_ms": round(g.ms.mean(), 1),
            "p95_latency_ms": round(g.ms.quantile(0.95), 1),
        })
    result = pd.DataFrame(summary)
    result.to_csv(OUT / "holdout_summary.csv", index=False)
    print()
    print(result.to_string(index=False))

    print("\n=== Full guardrail mistakes ===")
    g = df[df.baseline == "full_guardrail"]
    wrong = g[((g.label != "safe") & (~g.flagged)) | ((g.label == "safe") & (g.flagged))]
    for _, r in wrong.iterrows():
        resp = run_query(r.sql, execute=False)
        kind = "MISSED " + r.label if r.label != "safe" else "FALSE POSITIVE"
        print(f"\n[{kind}] {r.sql}")
        print(f"   decision={resp.decision} score={resp.score} reasons={resp.reasons}")


if __name__ == "__main__":
    main()
