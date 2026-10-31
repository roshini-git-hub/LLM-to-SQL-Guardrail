from pathlib import Path

import numpy as np
import pandas as pd

from app.guardrail import policy

R = Path("evaluation") / "results"
df = pd.read_csv(R / "cost_data.csv")

done = df[(~df["timed_out"]) & (df["time_ms"] > 0)]
timed = df[df["timed_out"]]

x = np.log(done["planner_cost"].values)
y = np.log(done["time_ms"].values)
slope, intercept = np.polyfit(x, y, 1)
pred = intercept + slope * x
r2 = 1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()
spread = float(np.exp(np.std(y - pred)))


def ms_for(cost):
    return float(np.exp(intercept + slope * np.log(cost)))


def cost_for(ms):
    return float(np.exp((np.log(ms) - intercept) / slope))


print(f"Fitted on {len(done)} queries that finished (timed-out queries excluded)")
print(f"  time_ms = exp({intercept:.2f}) * cost^{slope:.2f}   R^2 = {r2:.3f}")
print(f"  typical prediction is within a factor of {spread:.2f}")
print(f"  observed cost range of finished queries: {done.planner_cost.min():,.0f} to {done.planner_cost.max():,.0f}")
print(f"  most expensive finished query: cost {done.planner_cost.max():,.0f} ({done.loc[done.planner_cost.idxmax(), 'time_ms']:.0f} ms)")
if len(timed):
    print(f"  cheapest timed-out query: cost {timed.planner_cost.min():,.0f}")
else:
    print("  no query timed out in this data")

rows = []
print("\nYour current thresholds, in estimated real time:")
for name in ("COST_LOW", "COST_MEDIUM", "COST_HIGH"):
    c = getattr(policy, name)
    inside = done.planner_cost.min() <= c <= done.planner_cost.max()
    rows.append({"threshold": name, "cost_units": c, "estimated_ms": round(ms_for(c), 1),
                 "inside_observed_range": bool(inside)})
    flag = "" if inside else "   (outside the data, so this is an extrapolation)"
    print(f"  {name:12s} cost {c:>9,.0f}  ->  about {ms_for(c):,.0f} ms{flag}")

print("\nCost needed to reach a given running time:")
for target in (100, 1000, 5000):
    rows.append({"threshold": f"cost_for_{target}ms", "cost_units": round(cost_for(target)),
                 "estimated_ms": target, "inside_observed_range": ""})
    print(f"  {target:>5} ms  ->  cost about {cost_for(target):,.0f}")

pd.DataFrame(rows).to_csv(R / "threshold_calibration.csv", index=False)
print("\nSaved evaluation\\results\\threshold_calibration.csv")
