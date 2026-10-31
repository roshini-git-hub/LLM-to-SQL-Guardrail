### 6.7 Can a learned cost model beat the planner's estimate?

The guardrail uses the PostgreSQL planner's cost estimate as its measure of how heavy a query is. This
experiment asked whether a model trained on real execution times predicts slowness better. 321 generated
queries from 18 query shapes were run with `EXPLAIN (ANALYZE)` as the restricted
role, and plan features (cost, row estimates, node counts) were used to predict running time. 14 queries
hit the 5-second timeout and were recorded as 5,000 ms, so their real time is underestimated. A first
version of the data had no queries between planner cost 24,000 and 56 million, so 21 extra queries were
added to fill that range before the analysis below. The baseline was the planner cost calibrated by a
one-variable regression, so both models predict time in the same units.

| validation | model | spearman | mae_log | median_q_error | p90_q_error | auc_slow |
|---|---|---|---|---|---|---|
| random 5-fold (same query types) | Planner cost (calibrated) | 0.952 | 0.39 | 1.27 | 3.02 | 1.0 |
| random 5-fold (same query types) | Learned model | 0.976 | 0.128 | 1.08 | 1.4 | 1.0 |
| unseen query types | Planner cost (calibrated) | 0.962 | 0.43 | 1.31 | 3.68 | 1.0 |
| unseen query types | Learned model | 0.959 | 0.362 | 1.21 | 2.46 | 1.0 |

Spearman is rank correlation with the real time; "mae_log" is the mean absolute error of the log running
time; q-error is the factor by which the prediction is off (1 is perfect); AUC measures how well the
prediction separates slow from fast queries. On query shapes seen in training the learned model had
log error 0.128 against 0.39 for the
planner cost, but that estimate is optimistic because familiar shapes are recognised. With whole query
shapes held out, the stricter test, the log errors were 0.362 (learned)
and 0.43 (planner). The learned model relied mostly on the planner's own cost, which carried about 88% of its feature importance.

On unseen query shapes the learned model predicted running time more accurately than the calibrated planner cost (log error 0.362 against 0.43; 90th-percentile q-error 2.46 against 3.68), but it did not rank queries better (rank correlation 0.959 against 0.962) and the slow-versus-fast AUC was 1.0 for both, which is an easy distinction here because the slow queries cost far more than the fast ones. A guardrail only has to decide whether a query is heavy, and the planner cost already does that well; the learned model's advantage is in estimating how long a query will take. Because the data is small and comes from one schema, it was not added to the guardrail, and the result needs confirming before it is relied on.

**Checking the risk thresholds against measured time.** The thresholds in the guardrail were set by hand.
Fitting time against cost on the 307 queries that finished (R-squared 0.97) gives:

| Threshold | Planner cost | Estimated real time |
|---|---|---|
| COST_LOW | 20,000 | about 197 ms |
| COST_MEDIUM | 100,000 | about 821 ms |
| COST_HIGH | 500,000 | about 3,428 ms |

The cheapest query that hit the 5-second timeout had planner cost 458,569, and COST_HIGH (500,000) lies just above it. The fitted line predicts only about 3,175 ms for that query, which shows the fit underestimates running time at high costs: timed-out queries (true time unknown) had to be left out, and they are the slowest ones.

These estimates support the thresholds as reasonable, within the limits of a small workload on one schema
with freshly analysed statistics, which is the planner's best case. Stale statistics were not tested.

![Cost model](figures/cost_model.png)
