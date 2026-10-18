import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
)
cur = conn.cursor()

tests = [
    ("Allowed read",       "SELECT count(*) FROM orders"),
    ("Blocked column",     "SELECT email FROM customers LIMIT 1"),
    ("Blocked table",      "SELECT salary FROM employees LIMIT 1"),
    ("Blocked write",      "DELETE FROM orders WHERE order_id = 1"),
    ("Timeout (should stop after 5s)", "SELECT pg_sleep(10)"),
]

for label, sql in tests:
    try:
        cur.execute(sql)
        print(f"[OK]      {label}: {cur.fetchall() if cur.description else 'done'}")
    except Exception as e:
        print(f"[DENIED]  {label}: {str(e).splitlines()[0]}")
    conn.rollback()

conn.close()