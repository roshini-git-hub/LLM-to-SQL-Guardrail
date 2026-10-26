from app.guardrail.engine import run_query
from app.guardrail.llm import repair_sql
from app.guardrail.pipeline import ask

QUESTIONS = [
    "Show all order items",
    "List every order with its customer name",
    "Show the number of orders per customer",
    "Show total revenue for each product",
    "List all products with their category",
    "Show customers and the total they spent",
    "Show every order placed last month",
    "Which products have never been ordered?",
]

print("=== Natural questions (does the repair loop fire on its own?) ===")
for q in QUESTIONS:
    res = ask(q)
    print("\n" + q)
    print(f"  final={res.final.decision}  repairs_used={res.repairs_used}  attempts={len(res.attempts)}")
    if res.repairs_used:
        for i, a in enumerate(res.attempts, 1):
            print(f"  attempt {i}: {a.decision}  {a.sql}")
            for r in a.reasons:
                print(f"      - {r}")

print("\n=== Forced example (bad SQL supplied by us, repaired by the model) ===")
question = "How many customers are there in each city?"
bad_sql = "SELECT town, count(*) FROM customers GROUP BY town"
first = run_query(bad_sql, execute=False)
print("Bad SQL :", bad_sql)
print("Decision:", first.decision, first.reasons)
fixed = repair_sql(question, bad_sql, first.reasons)
print("Repaired:", fixed)
second = run_query(fixed)
print("Decision:", second.decision, "| rows:", len(second.rows), "| score:", second.score)
