-- Used ONLY by the benchmark (evaluation/run_nl.py) for the "model alone" setups.
-- It imitates a typical unprotected app account: it can read and write every table.
-- The benchmark runs its queries inside a transaction that is always rolled back.
--   psql -d <database> -v bench_password="$BENCH_PASSWORD" -f scripts/06_benchmark_role.sql
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bench_naive') THEN
        CREATE ROLE bench_naive LOGIN;
    END IF;
END $$;
ALTER ROLE bench_naive PASSWORD :'bench_password';
-- Like a table owner, it is not subject to row-level security.
ALTER ROLE bench_naive BYPASSRLS;
ALTER ROLE bench_naive SET statement_timeout = '5s';
GRANT USAGE ON SCHEMA public TO bench_naive;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO bench_naive;
