# Likely examiner questions and answers

Numbers below come from the final test set (rules frozen, run once) unless stated.

**1. Why not just use a read-only database role?**
The role is one layer in the system, and it is not enough alone. On the final set it stopped 66.7% of
unsafe queries, against 97.2% for the full guardrail. It lets expensive queries run until the timeout
(average 513.8 ms per query, p95 5,093.8 ms, versus 20.6 ms average for the guardrail's checks), it
allows information-disclosure queries such as server settings, and it cannot say why a query was refused.

**2. Why parse SQL into an AST instead of using keyword matching?**
A keyword blacklist detected only 11.1% of unsafe queries on the final set, because attacks can hide in
comments, mixed case, aliases, subqueries and CTEs. An AST lets the rules reason about what the query
actually touches: which tables, which columns, which functions and how many statements.

**3. Why EXPLAIN and not EXPLAIN ANALYZE?**
EXPLAIN ANALYZE executes the query, which defeats the purpose of checking before running. Plain EXPLAIN
only asks the planner for its estimate.

**4. Why use the maximum cost across plan nodes, not the root cost?**
A LIMIT can make the top of the plan look cheap while a join underneath is enormous. A cross join with
LIMIT 10 had a root cost that looked small but a node estimated at billions of rows.

**5. How were the risk thresholds chosen? Are they optimal?**
They were set by hand and are not learned. Hard rules (forbidden tables, statements, functions) always
block; soft signals add points; two fixed thresholds give ALLOW, REVIEW or BLOCK. This is a limitation.
A better approach is to tune them on labeled data using an ROC curve, and to learn cost from real execution times.

**6. Your false-positive rate on the final set was 19%. Why so high?**
Four of 21 safe queries were blocked, all for the same reason: harmless functions (nullif, trim, concat,
string_agg) were missing from the function allowlist. An allowlist is safe by default but blocks anything
unanticipated, which is a deliberate trade-off. I added those functions afterwards, which is why the
re-run is reported separately and is not independent.

**7. Did you really get 100% detection?**
Not on the independent test. The development and held-out sets reached 100%, but I tuned the rules on
them. The final set, run once with frozen rules (git tag final-eval-frozen), gave 97.2%: one unbounded
recursive query was missed. I report that number rather than the higher ones.

**8. How do you know the test sets are fair?**
They are small and written by hand, and their authorship is a limitation. The held-out and final sets
were written after the rules to use attack styles not tested before, and the final set was run exactly
once. TODO: state who wrote the queries and what assistance was used.

**9. Why are security violations never sent back to the LLM for repair?**
Otherwise a manipulated model could retry repeatedly and probe the policy. Only problems that can be
fixed safely (syntax, unknown column, high cost, missing LIMIT) are repaired, at most twice.

**10. Does the repair loop actually help?**
With the full prompt the model almost never needed repair. In a stress test where the first attempt was
given table names only, 4 of 20 first attempts were rejected, all 4 were fixed, and correctness rose from
65% to 85%. That is a small test under degraded conditions, so I do not generalize from it.

**11. What can your system not catch?**
A valid query that answers the wrong question (for example a wrongly spelled value such as 'Cancelled'
returning zero rows); inference attacks through aggregates on narrow filters; column tracing through
complex subqueries; and cases where the planner's estimates are wrong because statistics are stale.

**12. Is prompt injection handled?**
The guardrail checks the SQL, not the prompt, so it holds even if the model is manipulated. In the
natural-language test the model mostly refused unsafe requests itself, which measures the prompt, not
the guardrail. The guardrail is measured by the raw-SQL sets.

**13. What did the evaluation teach you?**
It found real bugs: AND, OR, CASE and CAST were treated as functions and blocked legitimate queries;
SELECT * over a table with hidden columns, FOR UPDATE and recursive queries were not covered by my own
rules and were only stopped by the database role or not at all. Each became a fix and a regression test.

**14. What is new here, given that SQL parsers and database roles already exist?**
The individual parts are known. The contribution is combining them into one pipeline with cost-based
risk scoring and a safe repair loop, then measuring each layer against simpler baselines and reporting
where each layer helps and where it fails.

**15. Why a local model?**
Privacy (queries and data stay on the machine), no cost, and repeatable results at temperature 0.
The trade-off is lower SQL quality than large hosted models. Model used: TODO (name, size, hardware).

**16. Would this scale to a real production database?**
Not unchanged. It was tested on one small schema. EXPLAIN is cheap but adds a round trip, the function
allowlist and column policy would need to be maintained per schema and per role, and statistics-based
cost estimates need care on large tables. Per-role policies and caching would be needed.

**17. What would you add with more time?**
A cost predictor trained on real execution times instead of planner estimates, PostgreSQL row-level
security, minimum group sizes for aggregates, per-role thresholds, and a larger independently written test set.

**18. What would you do differently?**
Have someone else write the test queries from the start, use real query logs as a workload, and keep
a frozen test set from the beginning instead of creating it after tuning.

**19. How is the audit log used?**
Every request, decision, score and reason is stored and shown on the dashboard. It supports review of
blocked queries and finding the rules that fire most often.

**20. How do I reproduce your results?**
README.md lists setup and commands: the database scripts, then python -m evaluation.run_eval, run_holdout,
run_final and run_nl, and pytest.

**21. Did you try a learned cost model?**
Yes, as an experiment. About 300 generated queries were run with EXPLAIN ANALYZE and a gradient
boosting model predicted running time from plan features. On query shapes it had seen it was much more
accurate than the calibrated planner cost, but on unseen shapes (the fair test) the result was mixed
and not clearly better, and it mostly relied on the planner's own cost. So I kept the planner cost
as the signal. Limits: small data from one schema, timed-out queries recorded as 5,000 ms, and
fresh statistics, which is the planner's best case. Stale statistics are the next experiment.

**22. How were your cost thresholds chosen?**
By hand. I later measured how planner cost relates to real running time on the test database
(see threshold calibration) to check what the thresholds mean in milliseconds. TODO: add the result.
