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

## Benchmark (qwen2.5:3b, 20 answerable + 6 unsafe questions per database)
| Database | Setup | Query ran | Correct | Unsafe let through | Avg latency |
|---|---|---|---|---|---|
| shop | small model alone | 90% | 85% | 3 of 6 | 0.62 s |
| shop | + guardrail, no repair | 95% | 75% | 0 of 6 | 0.87 s |
| shop | + guardrail + repair | 100% | 80% | 0 of 6 | 0.87 s |
| college | small model alone | 90% | 70% | 4 of 6 | 0.64 s |
| college | + guardrail, no repair | 100% | 80% | 0 of 6 | 0.98 s |
| college | + guardrail + repair | 100% | 80% | 0 of 6 | 0.98 s |

Honest reading:
- The clear win is safety (7 of 12 unsafe requests ran without the guardrail, 0 with it) and
  execution success (90% to 100%).
- Answer correctness is mixed: better on college (+10 points), slightly worse on shop (-5).
  The guarded prompt sometimes leads this small model to add an unnecessary join or filter.
- The repair loop was needed for only 1 of 40 answerable questions, so these sets do not
  stress it much. `evaluation/run_repair_stress.py` and `tests/test_repair.py` exercise it.
- No larger model was installed, so the "larger model alone" setup was not measured.
- The prompt wording about joins was adjusted once after the first college run, so the
  college numbers are not a fully untouched test.
- The 171 labelled SQL queries from the original evaluation still get the same verdicts.
