from pathlib import Path

import numpy as np
import pandas as pd

from app.guardrail.schema_loader import get_snapshot

_snap = get_snapshot()
_COSTS = {"COST_LOW": round(_snap.cost_low), "COST_MEDIUM": round(_snap.cost_medium),
          "COST_HIGH": round(_snap.cost_high)}

R = Path("evaluation") / "results"
OUT = Path("docs")
OUT.mkdir(exist_ok=True)

summary = pd.read_csv(R / "cost_model_summary.csv")
data = pd.read_csv(R / "cost_data.csv")
if (R / "cost_data_gap.csv").exists():
    data = pd.concat([data, pd.read_csv(R / "cost_data_gap.csv")], ignore_index=True)


def get(v, m, col):
    row = summary[summary["validation"].str.startswith(v) & summary["model"].str.startswith(m)].iloc[0]
    return row[col]


cols = list(summary.columns)
lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
for _, r in summary.iterrows():
    lines.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
table = "\n".join(lines)

n, to = len(data), int(data["timed_out"].sum())

# Calibration of planner cost against real time (finished queries only)
done = data[(~data["timed_out"]) & (data["time_ms"] > 0)]
timed = data[data["timed_out"]]
lx, ly = np.log(done["planner_cost"].values), np.log(done["time_ms"].values)
slope, intercept = np.polyfit(lx, ly, 1)
r2 = 1 - ((ly - (intercept + slope * lx)) ** 2).sum() / ((ly - ly.mean()) ** 2).sum()


def ms_for(c):
    return float(np.exp(intercept + slope * np.log(c)))


thr = []
for name in ("COST_LOW", "COST_MEDIUM", "COST_HIGH"):
    c = _COSTS[name]
    thr.append(f"| {name} | {c:,} | about {ms_for(c):,.0f} ms |")
thr_table = "| Threshold | Planner cost | Estimated real time |\n|---|---|---|\n" + "\n".join(thr)

timeout_text = ""
if len(timed):
    lowest = float(timed["planner_cost"].min())
    timeout_text = (
        f"The cheapest query that hit the 5-second timeout had planner cost {lowest:,.0f}, and COST_HIGH "
        f"({_COSTS['COST_HIGH']:,}) lies just above it. The fitted line predicts only about "
        f"{ms_for(lowest):,.0f} ms for that query, which shows the fit underestimates running time at high "
        "costs: timed-out queries (true time unknown) had to be left out, and they are the slowest ones."
    )

# Verdict is computed from the numbers, not assumed
def val(v, m, col):
    return float(get(v, m, col))


err_l, err_p = val("unseen", "Learned", "mae_log"), val("unseen", "Planner", "mae_log")
q_l, q_p = val("unseen", "Learned", "p90_q_error"), val("unseen", "Planner", "p90_q_error")
sp_l, sp_p = val("unseen", "Learned", "spearman"), val("unseen", "Planner", "spearman")
auc_l = val("unseen", "Learned", "auc_slow") if "auc_slow" in summary.columns else None
auc_p = val("unseen", "Planner", "auc_slow") if "auc_slow" in summary.columns else None

more_accurate = err_l < 0.9 * err_p and q_l < q_p
rank_tied = abs(sp_l - sp_p) <= 0.02
auc_tied = auc_l is None or abs(auc_l - auc_p) <= 0.01

if auc_l is None:
    auc_text = ""
elif auc_l == auc_p:
    auc_text = (f" and the slow-versus-fast AUC was {auc_l} for both, which is an easy distinction here "
                "because the slow queries cost far more than the fast ones")
else:
    auc_text = f" and the slow-versus-fast AUC was {auc_l} against {auc_p}"

if more_accurate and rank_tied and auc_tied:
    verdict = (
        f"On unseen query shapes the learned model predicted running time more accurately than the "
        f"calibrated planner cost (log error {err_l} against {err_p}; 90th-percentile q-error {q_l} "
        f"against {q_p}), but it did not rank queries better (rank correlation {sp_l} against {sp_p})"
        f"{auc_text}. A guardrail only has to decide whether a query is heavy, and the planner cost "
        "already does that well; the learned model's advantage is in estimating how long a query will "
        "take. Because the data is small and comes from one schema, it was not added to the guardrail, "
        "and the result needs confirming before it is relied on."
    )
elif (not more_accurate) and rank_tied and auc_tied:
    verdict = (
        f"On unseen query shapes the learned model was no more accurate than the calibrated planner cost "
        f"(log error {err_l} against {err_p}; rank correlation {sp_l} against {sp_p}){auc_text}, so it "
        "was not added to the guardrail."
    )
else:
    verdict = (
        f"On unseen query shapes the results were mixed (log error {err_l} against {err_p}; "
        f"90th-percentile q-error {q_l} against {q_p}; rank correlation {sp_l} against {sp_p})"
        f"{auc_text}. There is no dependable advantage, so the learned model was not added to the guardrail."
    )

imp_text = ""
if (R / "cost_model_importance.csv").exists():
    imp = pd.read_csv(R / "cost_model_importance.csv", index_col=0).iloc[:, 0]
    imp_text = (f"The learned model relied mostly on the planner's own cost, which carried about "
                f"{round(100 * float(imp.get('planner_cost', 0)))}% of its feature importance.")

text = f"""### 6.7 Can a learned cost model beat the planner's estimate?

The guardrail uses the PostgreSQL planner's cost estimate as its measure of how heavy a query is. This
experiment asked whether a model trained on real execution times predicts slowness better. {n} generated
queries from {data['template'].nunique()} query shapes were run with `EXPLAIN (ANALYZE)` as the restricted
role, and plan features (cost, row estimates, node counts) were used to predict running time. {to} queries
hit the 5-second timeout and were recorded as 5,000 ms, so their real time is underestimated. A first
version of the data had no queries between planner cost 24,000 and 56 million, so 21 extra queries were
added to fill that range before the analysis below. The baseline was the planner cost calibrated by a
one-variable regression, so both models predict time in the same units.

{table}

Spearman is rank correlation with the real time; "mae_log" is the mean absolute error of the log running
time; q-error is the factor by which the prediction is off (1 is perfect); AUC measures how well the
prediction separates slow from fast queries. On query shapes seen in training the learned model had
log error {get('random', 'Learned', 'mae_log')} against {get('random', 'Planner', 'mae_log')} for the
planner cost, but that estimate is optimistic because familiar shapes are recognised. With whole query
shapes held out, the stricter test, the log errors were {get('unseen', 'Learned', 'mae_log')} (learned)
and {get('unseen', 'Planner', 'mae_log')} (planner). {imp_text}

{verdict}

**Checking the risk thresholds against measured time.** The thresholds in the guardrail were set by hand.
Fitting time against cost on the {len(done)} queries that finished (R-squared {r2:.2f}) gives:

{thr_table}

{timeout_text}

These estimates support the thresholds as reasonable, within the limits of a small workload on one schema
with freshly analysed statistics, which is the planner's best case. Stale statistics were not tested.

![Cost model](figures/cost_model.png)
"""

(OUT / "cost_model_section.md").write_text(text, encoding="utf-8")
print("Wrote docs\\cost_model_section.md")
