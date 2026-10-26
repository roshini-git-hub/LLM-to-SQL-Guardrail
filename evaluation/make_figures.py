from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

R = Path("evaluation") / "results"
F = Path("docs") / "figures"
F.mkdir(parents=True, exist_ok=True)

ORDER = ["no_guardrail", "regex_blacklist", "db_role_only", "ast_only", "full_guardrail"]
SETS = {
    "development": ("summary.csv", "Development set"),
    "held_out": ("holdout_before_fix.csv", "Held-out set (first run, before tuning)"),
    "final": ("final_summary_frozen.csv", "Final set (rules frozen)"),
}

for key, (fname, title) in SETS.items():
    p = R / fname
    if not p.exists():
        print("skipping", fname)
        continue
    df = pd.read_csv(p).set_index("baseline").reindex(ORDER)

    ax = df[["detection_rate", "false_positive_rate"]].plot(
        kind="bar", figsize=(8, 4.5), color=["#2f6fed", "#e5534b"], width=0.75)
    ax.set_ylabel("Percent")
    ax.set_xlabel("")
    ax.set_ylim(0, 108)
    ax.set_title(title)
    ax.legend(["Detection rate", "False-positive rate"])
    for container in ax.containers:
        ax.bar_label(container, fmt="%.1f", fontsize=8, padding=2)
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    plt.savefig(F / f"{key}_detection.png", dpi=160)
    plt.close()

# Latency on the final set (log scale; approaches with 0 ms are omitted)
p = R / "final_summary_frozen.csv"
if p.exists():
    df = pd.read_csv(p).set_index("baseline").reindex(ORDER)
    lat = df[df["avg_latency_ms"] > 0]["avg_latency_ms"]
    ax = lat.plot(kind="bar", figsize=(7, 4), color="#7c5cff", logy=True)
    ax.set_ylabel("Average latency (ms, log scale)")
    ax.set_xlabel("")
    ax.set_title("Time cost per query (final set)")
    for container in ax.containers:
        ax.bar_label(container, fmt="%.1f", fontsize=8, padding=2)
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    plt.savefig(F / "final_latency.png", dpi=160)
    plt.close()

print("Figures written to", F)
