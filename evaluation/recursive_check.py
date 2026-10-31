import time

from app.guardrail.db import get_connection
from app.guardrail.engine import run_query

REC = "WITH RECURSIVE x AS (SELECT 1 AS n UNION ALL SELECT n + 1 FROM x) "


def timed(sql):
    conn = get_connection()
    start = time.time()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        result = f"{len(cur.fetchall())} rows returned"
    except Exception as e:
        result = "stopped: " + str(e).splitlines()[0]
    finally:
        conn.rollback()
        conn.close()
    return result, round(time.time() - start, 2)


print("Current guardrail decision:", run_query(REC + "SELECT * FROM x", execute=False).decision)

for label, inner in [("rows selected", REC + "SELECT * FROM x"),
                     ("rows counted", REC + "SELECT count(*) FROM x")]:
    result, secs = timed(f"SELECT * FROM ({inner}) AS guarded LIMIT 1000")
    print(f"As the frozen engine would have run it ({label}): {result} after {secs} s")
