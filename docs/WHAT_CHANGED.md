# Dynamic guardrail: summary for presentation

## What changed
- **No hard-coded schema.** `schema_loader.py` reads tables, columns, privileges, foreign keys,
  RLS policies, table sizes and sensitive-column comments from PostgreSQL for the connected role
  and returns a cached `SchemaSnapshot`. `policy.py` keeps only generic settings.
- **Multi-user.** The API takes a role (`role` field or `X-DB-Role` header) and uses `SET ROLE`,
  so each user gets their own snapshot, GRANTs and row-level security.
- **Automatic refresh.** An event trigger sends `NOTIFY schema_changed` after any DDL, GRANT,
  REVOKE or COMMENT; the guardrail `LISTEN`s and reloads. Revoking a grant blocks the table
  about one second later with no restart.
- **Schema-aware repair.** The LLM prompt is built from the snapshot (visible columns and FK
  joins only). Fixable errors get precise hints (real column list, closest names via difflib,
  join condition). MySQL / SQL Server syntax is transpiled by SQLGlot before any LLM retry.
  Security violations are never sent back. Max 2 repairs, every attempt logged.
- **Engineering fixes.** Connection pool, credentials in `.env`, LIMIT injected through the AST,
  UTF-8 requirements, duplicate policy block removed.
- **Integration.** MCP server with `ask_database`, `run_sql`, `describe_schema`.
- **Proof it is generic.** A second database (college) runs on the same code via `DB_NAME`.

## DBMS concepts used
| Concept | Where |
|---|---|
| System catalogs (`pg_class`, `pg_attribute`, `pg_constraint`, `pg_policies`, `pg_stats`) | `schema_loader.py` |
| GRANT / REVOKE at table and column level, `has_column_privilege` | snapshot, `scripts/03`, `04` |
| Roles, role membership, `SET ROLE`, `WITH INHERIT FALSE` | `db.py`, `scripts/04_demo_roles.sql` |
| Row-Level Security (policies, chained through subqueries) | `scripts/04_demo_roles.sql` |
| Event triggers (`ddl_command_end`) | `scripts/05_schema_events.sql` |
| LISTEN / NOTIFY | `schema_loader.start_listener` |
| EXPLAIN plans and planner cost model (seq_page_cost, cpu_tuple_cost) | `cost.py`, size-relative thresholds |
| Planner statistics (`reltuples`, `relpages`, `n_distinct`) | thresholds and value hints |
| Connection pooling | `db.py` (`psycopg2.pool.ThreadedConnectionPool`) |
| Read-only transactions and `statement_timeout` | connection options in `db.py` |
| Foreign keys | join hints in prompts and repair feedback |

## Benchmark (qwen2.5:3b small, qwen2.5:7b large; 20 answerable + 6 unsafe questions per database)
| Database | Setup | Query ran | Correct | Unsafe let through | Avg repairs |
|---|---|---|---|---|---|
| shop | small model alone | 90% | 90% | 3 of 6 | 0 |
| shop | small + guardrail, no repair | 95% | 75% | 0 of 6 | 0 |
| shop | small + guardrail + repair | 100% | 80% | 0 of 6 | 0.05 |
| shop | larger model alone | 95% | 85% | 3 of 6 | 0 |
| college | small model alone | 90% | 65% | 4 of 6 | 0 |
| college | small + guardrail, no repair | 90% | 70% | 0 of 6 | 0 |
| college | small + guardrail + repair | 100% | 75% | 0 of 6 | 0.1 |
| college | larger model alone | 95% | 90% | 4 of 6 | 0 |

Honest reading:
- The clear win is safety. Without the guardrail 7 of 12 unsafe requests ran, for the small
  AND the larger model. A bigger model does not fix this; the guardrail does (0 of 12).
- The guardrail is the only setup where every answerable query ran (100%, vs 90-95%).
- Answer correctness is mixed: +10 points on college, -10 on shop for the small model. The
  guarded prompt sometimes leads this small model to add an unnecessary join or filter.
- The larger model alone is more correct on college (90% vs 75%), so the guardrail does not
  make a small model as accurate as a larger one. It makes it safe and reliable to execute.
- The repair loop was needed for 3 of 40 answerable questions and fixed execution in each
  case (shop 95% to 100%, college 90% to 100%).
- Results vary by about one question (5 points) between runs: an earlier run gave small alone
  85% / 70% and guarded 80% / 80% (shop / college).
- Latency is not reported: on this 8 GB machine the two models were swapped in and out of
  memory during the run, so the timings in the CSVs (2 to 7 s) are not meaningful. With only
  the small model loaded, earlier runs took about 0.6 s alone and 0.9 s with the guardrail.
- The prompt wording about joins was adjusted once after the first college run, so the
  college numbers are not a fully untouched test.
- The 171 labelled SQL queries from the original evaluation still get the same verdicts.
