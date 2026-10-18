import json
from pathlib import Path

import pandas as pd

from evaluation.baselines import BASELINES
from evaluation.dataset import DATASET

OUT = Path("evaluation") / "results"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, fn in BASELINES.items():
        print(f"Running baseline: {name} ...")
        for sql, label in DATASET:
            flagged, ms = fn(sql)
            rows.append({"baseline": name, "label": label, "sql": sql,
                         "flagged": bool(flagged), "ms": round(ms, 2)})

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "per_query.csv", index=False)

    summary = []
    for name, g in df.groupby("baseline", sort=False):
        safe = g[g.label == "safe"]
        malicious = g[g.label == "malicious"]
        expensive = g[g.label == "expensive"]
        unsafe = g[g.label != "safe"]

        tp = int(unsafe.flagged.sum())
        fp = int(safe.flagged.sum())
        precision = tp / (tp + fp) if (tp + fp) else 0.0

        summary.append({
            "baseline": name,
            "detection_rate": round(100 * tp / len(unsafe), 1),
            "malicious_detected": round(100 * malicious.flagged.mean(), 1),
            "expensive_detected": round(100 * expensive.flagged.mean(), 1),
            "false_positive_rate": round(100 * fp / len(safe), 1),
            "precision": round(100 * precision, 1),
            "avg_latency_ms": round(g.ms.mean(), 1),
            "p95_latency_ms": round(g.ms.quantile(0.95), 1),
        })

    result = pd.DataFrame(summary)
    result.to_csv(OUT / "summary.csv", index=False)
    with open(OUT / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print()
    print(result.to_string(index=False))
    print(f"\nSaved results to {OUT}")


if __name__ == "__main__":
    main()
