import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.guardrail.engine import run_query

QUERIES = [
    "SELECT name, city FROM customers LIMIT 5",
    "SELECT status, count(*) FROM orders GROUP BY status",
    "SELECT o.status, sum(oi.unit_price * oi.quantity) FROM orders o JOIN order_items oi ON o.order_id = oi.order_id GROUP BY o.status",
    "SELECT * FROM order_items",
    "SELECT c.name, oi.quantity FROM customers c, order_items oi LIMIT 10",
    "SELECT salary FROM employees",
    "SELECT name FROM customers WHERE nonexistent_col = 1",
]

for q in QUERIES:
    r = run_query(q)
    print("=" * 80)
    print(q)
    print(f"  -> {r.decision}  (risk score {r.score})")
    for reason in r.reasons:
        print(f"     - {reason}")
    if r.rows:
        print(f"     returned {len(r.rows)} rows in {r.elapsed_ms:.1f} ms")
