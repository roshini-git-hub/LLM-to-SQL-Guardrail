# Demo script (about 5 minutes)

Before starting: Ollama running, `uvicorn app.main:app` running, `streamlit run dashboard\Home.py` open.

1. The problem (30 s)
   An LLM writes SQL. It can be wrong, unauthorized or expensive. The database role alone
   only partly helps.

2. A normal question (45 s) - page "Ask a question"
   "How many orders are there for each status?"
   Show: ALLOW, the SQL the model wrote, the risk score, the rows, the execution time.

3. An expensive query (60 s) - page "Analyze SQL"
   SELECT c.name, oi.quantity FROM customers c, order_items oi LIMIT 10
   Show: BLOCK, the reasons (no join condition, huge row estimate, very high cost).
   Point out: the LIMIT hides the cost at the top of the plan; the guardrail looks at every plan step.

4. Attacks (60 s) - page "Analyze SQL", one at a time
   SELECT name FROM customers; DROP TABLE orders          (stacked statement)
   SELECT salary FROM employees                            (protected table)
   SELECT * FROM customers LIMIT 5                         (star would expose email and phone)
   SELECT pg_sleep(10)                                     (dangerous function)
   Show the reason each one is stopped.

5. A legitimate query that is not blocked (30 s)
   SELECT name, CASE WHEN price > 500 THEN 'high' ELSE 'low' END AS tier FROM products LIMIT 20
   Point out: low false positives matter as much as detection.

6. The repair loop (45 s) - see Step 77 for the example to use.
   Show the attempts: first rejected with a reason, then corrected and allowed.
   Point out: security violations are never sent back for repair.

7. Results (60 s) - page "Evaluation"
   Compare the five approaches on the final set; show detection, false positives and latency.
   Mention honestly: what the evaluation found and fixed, and what is still a limitation.

8. Audit log (15 s) - page "Audit log"
   Everything just shown has been recorded.

