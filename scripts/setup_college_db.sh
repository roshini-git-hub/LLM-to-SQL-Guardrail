#!/usr/bin/env bash
# Creates the second demo database (college_db). Run scripts/setup_db.sh first:
# it creates the guardrail_ro login role that this database reuses.
# Usage: bash scripts/setup_college_db.sh
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a

ADMIN="${ADMIN_USER:-$USER}"
export PGHOST="${DB_HOST:-localhost}" PGPORT="${DB_PORT:-5432}" PGUSER="$ADMIN"
[ -n "${ADMIN_PASSWORD:-}" ] && export PGPASSWORD="$ADMIN_PASSWORD"
DB=college_db

dropdb --if-exists "$DB"
createdb "$DB"
for f in scripts/college/01_schema.sql scripts/college/02_seed.sql scripts/college/03_roles.sql scripts/05_schema_events.sql; do
  psql -d "$DB" -q -v ON_ERROR_STOP=1 -f "$f"
done
if [ -n "${BENCH_PASSWORD:-}" ]; then
  psql -d "$DB" -q -v ON_ERROR_STOP=1 -v bench_password="$BENCH_PASSWORD" -f scripts/06_benchmark_role.sql
fi
echo "Database $DB is ready. Point the guardrail at it with DB_NAME=$DB"
