from pathlib import Path

import pandas as pd

R = Path("evaluation") / "results"
OUT = Path("docs")
OUT.mkdir(exist_ok=True)

summary = pd.read_csv(R / "cost_model_summary.csv")
data = pd.read_csv(R / "cost_data.csv")


def get(validation_start, model_start, col):
    row = summary[summary["validation"].str.startswith(validation_start)
                  & summary["model"].str.startswith(model_start)].iloc[0]
    return row[col]


cols = list(summary.columns)
lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
for _, r in summary.iterrows():
    lines.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
table = "\n".join(lines)

n, to = len(data), int(data["timed_out"].sum())

text = f"""### 6.7 Can a learned cost model beat the planner's estimate?

The guardrail uses the PostgreSQL planner's cost estimate as its measure of how heavy a query is.
This experiment asked whether a model trained on real execution times predicts slowness better.
{n} generated queries from {data['template'].nunique()} query shapes were run through
`EXPLAIN (ANALYZE)` as the restricted role, and plan features (cost, row estimates, node counts) were
used to predict running time. {to} queries hit the 5-second timeout and were recorded as 5,000 ms, so
their real time is underestimated. The baseline was the planner cost calibrated by a one-variable
regression, so that both models predict time in the same units.

{table}

Spearman is rank correlation with the real time; "error (log)" is mean absolute error of the log
running time; q-error is the factor by which the prediction is off (1 is perfect); AUC measures how
well the prediction separates slow from fast queries.

On query shapes seen during training, the learned model was clearly more accurate (log error
{get('random', 'Learned', 'mae_log')} against {get('random', 'Planner', 'mae_log')}). This is an optimistic
estimate, because the model can recognise familiar shapes. When whole query shapes were held out, the
stricter test, the results were mixed: rank correlation ({get('unseen', 'Learned', 'spearman')} against
{get('unseen', 'Planner', 'spearman')}) and q-error were slightly better, but log error
({get('unseen', 'Learned', 'mae_log')} against {get('unseen', 'Planner', 'mae_log')}) and the AUC for slow
queries ({get('unseen', 'Learned', 'auc_slow')} against {get('unseen', 'Planner', 'auc_slow')}) were worse.
The learned model's own feature importance was dominated by the planner's cost (about 87%).

Conclusion: on this small workload with freshly analyzed statistics, the planner's cost was already a
reliable signal, and the learned model gave no dependable advantage on unseen query shapes, so it was
not added to the guardrail. The result does not show that learned models cannot help: the planner is
expected to be less reliable when statistics are stale or columns are correlated, which was not tested,
and the data is small and comes from one schema. TODO: re-check this paragraph if the experiment is re-run.

![Cost model](figures/cost_model.png)
"""

(OUT / "cost_model_section.md").write_text(text, encoding="utf-8")
print("Wrote docs\\cost_model_section.md")
