from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold, KFold, cross_val_predict

R = Path("evaluation") / "results"
F = Path("docs") / "figures"
F.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(R / "cost_data.csv")
if (R / "cost_data_gap.csv").exists():
    df = pd.concat([df, pd.read_csv(R / "cost_data_gap.csv")], ignore_index=True)
true_ms = df["time_ms"].values
y = np.log1p(true_ms)

feature_cols = [c for c in df.columns if c not in ("sql", "template", "time_ms", "timed_out")]
X = np.log1p(df[feature_cols].values)
X_cost = np.log1p(df[["planner_cost"]].values)
groups = df["template"].values

# Threshold for "slow": the first of these that leaves at least 10 queries on each side
slow_thr = None
for cand in (1000, 500, 200, 100, 50):
    pos = int((true_ms >= cand).sum())
    if pos >= 10 and len(df) - pos >= 10:
        slow_thr = cand
        break
print(f"Queries: {len(df)}   timed out: {int(df.timed_out.sum())}   'slow' threshold: {slow_thr} ms")


def qerror(pred_ms, truth_ms):
    p, t = np.maximum(pred_ms, 1.0), np.maximum(truth_ms, 1.0)
    return np.maximum(p / t, t / p)


def score(validation, model, pred_log):
    q = qerror(np.expm1(pred_log), true_ms)
    row = {
        "validation": validation,
        "model": model,
        "spearman": round(float(spearmanr(pred_log, y).correlation), 3),
        "mae_log": round(float(np.mean(np.abs(pred_log - y))), 3),
        "median_q_error": round(float(np.median(q)), 2),
        "p90_q_error": round(float(np.percentile(q, 90)), 2),
    }
    if slow_thr:
        row["auc_slow"] = round(float(roc_auc_score(true_ms >= slow_thr, pred_log)), 3)
    return row


splits = {
    "random 5-fold (same query types)": KFold(5, shuffle=True, random_state=0),
    "unseen query types": GroupKFold(n_splits=min(5, len(set(groups)))),
}

rows, kept = [], {}
for name, cv in splits.items():
    kw = {"groups": groups} if isinstance(cv, GroupKFold) else {}
    p_cost = cross_val_predict(LinearRegression(), X_cost, y, cv=cv, **kw)
    p_model = cross_val_predict(
        GradientBoostingRegressor(n_estimators=200, max_depth=3, random_state=0), X, y, cv=cv, **kw)
    rows.append(score(name, "Planner cost (calibrated)", p_cost))
    rows.append(score(name, "Learned model", p_model))
    kept[name] = (p_cost, p_model)

summary = pd.DataFrame(rows)
summary.to_csv(R / "cost_model_summary.csv", index=False)
print()
print(summary.to_string(index=False))

model = GradientBoostingRegressor(n_estimators=200, max_depth=3, random_state=0).fit(X, y)
imp = pd.Series(model.feature_importances_, index=feature_cols).sort_values(ascending=False)
imp.to_csv(R / "cost_model_importance.csv")
print("\nMost influential plan features:")
print(imp.head(8).round(3).to_string())

# Figure: unseen query types
p_cost, p_model = kept["unseen query types"]
fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
axes[0].scatter(df["planner_cost"], true_ms, s=14, alpha=0.7, color="#e5534b")
axes[0].set_xscale("log")
axes[0].set_yscale("log")
axes[0].set_xlabel("Planner cost estimate")
axes[0].set_ylabel("Actual time (ms)")
axes[0].set_title("Planner cost vs actual time")

axes[1].scatter(np.expm1(p_model), true_ms, s=14, alpha=0.7, color="#2f6fed")
lim = [1, max(true_ms.max(), np.expm1(p_model).max())]
axes[1].plot(lim, lim, color="gray", linestyle="--", linewidth=1)
axes[1].set_xscale("log")
axes[1].set_yscale("log")
axes[1].set_xlabel("Predicted time (ms), unseen query types")
axes[1].set_ylabel("Actual time (ms)")
axes[1].set_title("Learned model vs actual time")
plt.tight_layout()
plt.savefig(F / "cost_model.png", dpi=160)
print("\nFigure saved to docs\\figures\\cost_model.png")

