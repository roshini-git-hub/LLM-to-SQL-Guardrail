import json
import random
from pathlib import Path

import pandas as pd

from app.guardrail.db import get_connection

random.seed(7)
OUT = Path("evaluation") / "results"
OUT.mkdir(parents=True, exist_ok=True)
N_QUERIES = 300

CITIES = ["Hyderabad", "Chennai", "Mumbai", "Delhi", "Bengaluru"]
STATUSES = ["placed", "shipped", "delivered", "cancelled"]


def r(a, b):
    return random.randint(a, b)


# (weight, generator). Heavier and rarer templates get smaller weights.
TEMPLATES = [
    (3, lambda: f"SELECT order_id, total_amount FROM orders WHERE total_amount > {r(0, 5000)} LIMIT {r(10, 1000)}"),
    (3, lambda: f"SELECT status, count(*) FROM orders WHERE total_amount > {r(0, 5000)} GROUP BY status"),
    (3, lambda: f"SELECT count(*) FROM order_items WHERE quantity >= {r(1, 5)}"),
    (3, lambda: f"SELECT c.city, count(*) FROM customers c JOIN orders o ON o.customer_id = c.customer_id WHERE o.status = '{random.choice(STATUSES)}' GROUP BY c.city"),
    (3, lambda: f"SELECT p.category, sum(oi.quantity * oi.unit_price) FROM order_items oi JOIN products p ON p.product_id = oi.product_id WHERE oi.quantity >= {r(1, 5)} GROUP BY p.category"),
    (3, lambda: f"SELECT o.order_id, c.name FROM orders o JOIN customers c ON c.customer_id = o.customer_id WHERE o.total_amount > {r(0, 5000)} ORDER BY o.total_amount DESC LIMIT {r(5, 500)}"),
    (3, lambda: f"SELECT c.name, p.category, oi.quantity FROM order_items oi JOIN orders o ON o.order_id = oi.order_id JOIN customers c ON c.customer_id = o.customer_id JOIN products p ON p.product_id = oi.product_id WHERE o.status = '{random.choice(STATUSES)}' LIMIT {r(10, 2000)}"),
    (3, lambda: f"SELECT * FROM order_items ORDER BY unit_price DESC LIMIT {r(10, 5000)}"),
    (3, lambda: f"SELECT customer_id, sum(total_amount) FROM orders GROUP BY customer_id HAVING sum(total_amount) > {r(1000, 30000)} ORDER BY 2 DESC LIMIT {r(5, 200)}"),
    (2, lambda: f"SELECT c.name, p.name FROM customers c, products p LIMIT {r(10, 5000)}"),
    (2, lambda: f"SELECT count(*) FROM customers c, products p WHERE c.customer_id % {r(50, 400)} = p.product_id % {r(50, 400)}"),
    (2, lambda: f"SELECT count(*) FROM orders a JOIN orders b ON a.total_amount = b.total_amount WHERE a.total_amount > {r(0, 4900)}"),
    (1, lambda: f"SELECT count(*) FROM order_items a JOIN order_items b ON a.quantity = b.quantity WHERE a.item_id < {r(1000, 600000)}"),
    (3, lambda: f"SELECT date_trunc('month', order_date), count(*) FROM orders WHERE status = '{random.choice(STATUSES)}' GROUP BY 1 ORDER BY 1"),
    (3, lambda: f"SELECT name, price FROM products WHERE price BETWEEN {r(10, 400)} AND {r(401, 1000)}"),
    (3, lambda: f"SELECT c.name FROM customers c WHERE c.customer_id IN (SELECT customer_id FROM orders WHERE total_amount > {r(0, 5000)}) LIMIT {r(10, 2000)}"),
]

NODE_TYPES = [
    "Seq Scan", "Index Scan", "Index Only Scan", "Bitmap Heap Scan", "Hash Join",
    "Nested Loop", "Merge Join", "Hash", "Sort", "Aggregate", "HashAggregate",
    "GroupAggregate", "Limit", "Gather", "Materialize",
]


def generate():
    seen, rows = set(), []
    ids = list(range(len(TEMPLATES)))
    weights = [w for w, _ in TEMPLATES]
    tries = 0
    while len(rows) < N_QUERIES and tries < N_QUERIES * 30:
        tries += 1
        t = random.choices(ids, weights)[0]
        sql = TEMPLATES[t][1]()
        if sql not in seen:
            seen.add(sql)
            rows.append((t, sql))
    return rows


def walk(node, out):
    out.append(node)
    for child in node.get("Plans", []):
        walk(child, out)


def features(root):
    nodes = []
    walk(root, nodes)
    f = {
        "planner_cost": root["Total Cost"],
        "max_cost": max(n["Total Cost"] for n in nodes),
        "root_rows": root.get("Plan Rows", 0),
        "max_rows": max(n.get("Plan Rows", 0) for n in nodes),
        "plan_width": root.get("Plan Width", 0),
        "n_nodes": len(nodes),
        "n_relations": sum(1 for n in nodes if "Relation Name" in n),
        "seq_scan_rows": sum(n.get("Plan Rows", 0) for n in nodes if n["Node Type"] == "Seq Scan"),
    }
    for t in NODE_TYPES:
        f["n_" + t.lower().replace(" ", "_")] = sum(1 for n in nodes if n["Node Type"] == t)
    return f


def explain(sql, analyze):
    conn = get_connection()
    try:
        cur = conn.cursor()
        prefix = "EXPLAIN (ANALYZE, FORMAT JSON) " if analyze else "EXPLAIN (FORMAT JSON) "
        cur.execute(prefix + sql)
        raw = cur.fetchone()[0]
        if isinstance(raw, str):
            raw = json.loads(raw)
        return raw[0], None
    except Exception as e:
        return None, str(e)
    finally:
        conn.rollback()
        conn.close()


def measure(sql):
    top, err = explain(sql, True)
    if top is not None:
        t1 = top["Execution Time"]
        again, _ = explain(sql, True)
        t = min(t1, again["Execution Time"]) if again is not None else t1
        return top["Plan"], t, False
    if err and ("timeout" in err or "canceling statement" in err):
        top, _ = explain(sql, False)
        if top is not None:
            return top["Plan"], 5000.0, True
    return None, None, False


def main():
    queries = generate()
    print(f"Generated {len(queries)} queries")
    records = []
    for i, (template, sql) in enumerate(queries, 1):
        plan, t, timed_out = measure(sql)
        if plan is None:
            continue
        rec = {"sql": sql, "template": template, "time_ms": round(t, 3), "timed_out": timed_out}
        rec.update(features(plan))
        records.append(rec)
        if i % 25 == 0:
            print(f"  {i}/{len(queries)} done ({len(records)} usable)")

    df = pd.DataFrame(records)
    df.to_csv(OUT / "cost_data.csv", index=False)
    print()
    print("Usable queries:", len(df))
    print("Timed out (recorded as 5000 ms):", int(df.timed_out.sum()))
    print(df.time_ms.describe().round(1).to_string())


if __name__ == "__main__":
    main()
