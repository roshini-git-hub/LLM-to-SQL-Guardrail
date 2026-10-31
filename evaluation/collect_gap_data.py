from pathlib import Path

import pandas as pd

from evaluation.collect_cost_data import features, measure

OUT = Path("evaluation") / "results"

queries = []
for x in (20, 30, 50, 80, 120, 200, 300, 500, 800, 1200, 2000, 3000, 5000, 8000):
    queries.append((100, f"SELECT count(*) FROM customers c CROSS JOIN order_items oi WHERE oi.item_id < {x}"))
for x in (1000, 3000, 10000, 30000, 100000, 300000, 600000):
    queries.append((101, f"SELECT count(*) FROM products p CROSS JOIN order_items oi WHERE oi.item_id < {x}"))

records = []
for i, (template, sql) in enumerate(queries, 1):
    print(f"[{i}/{len(queries)}] {sql}")
    plan, t, timed_out = measure(sql)
    if plan is None:
        print("   skipped (could not be measured)")
        continue
    rec = {"sql": sql, "template": template, "time_ms": round(t, 3), "timed_out": timed_out}
    rec.update(features(plan))
    records.append(rec)

df = pd.DataFrame(records)
df.to_csv(OUT / "cost_data_gap.csv", index=False)

print("\nPlanner cost versus real time for the new queries:")
show = df.sort_values("planner_cost")[["planner_cost", "time_ms", "timed_out"]].copy()
show["planner_cost"] = show["planner_cost"].round(0).astype(int)
print(show.to_string(index=False))
