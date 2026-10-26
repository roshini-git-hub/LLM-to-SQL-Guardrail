### 6.6 Repair-loop stress test

With the full prompt the model rarely made correctable mistakes (a spot check of eight further
questions needed no repair at all), so the repair loop was also tested under a deliberately degraded
condition. For these 20 questions the model's first attempt was given only the table names, not the
columns, so wrong column names were likely. Repairs then received the rejected query and the
reasons it was rejected, together with the full schema prompt.

| Questions | Correct on first attempt | Correct after repair | Rejected on first attempt | Rescued by repair | Still wrong |
|---|---|---|---|---|---|
| 20 | 65.0% | 85.0% | 4 | 4 | 3 |

Only problems the guardrail can detect are repaired (for example a column that does not exist). A
query that is valid but answers the wrong question is allowed through unchanged, so the repair
loop cannot improve those. This is a stress test under degraded conditions, not the system's normal operating mode.
