#!/usr/bin/env bash
# Creates the demo database and the read-only guardrail role.
# Reads DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT from .env.
# Usage: bash scripts/setup_db.sh
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a

ADMIN="${ADMIN_USER:-$USER}"
export PGHOST="${DB_HOST:-localhost}" PGPORT="${DB_PORT:-5432}" PGUSER="$ADMIN"
[ -n "${ADMIN_PASSWORD:-}" ] && export PGPASSWORD="$ADMIN_PASSWORD"

dropdb --if-exists "$DB_NAME"
for r in analyst city_manager support guardrail_ro; do
  psql -d postgres -qc "DROP ROLE IF EXISTS $r" 2>/dev/null || true
done
createdb "$DB_NAME"
psql -d "$DB_NAME" -q -v ON_ERROR_STOP=1 -f scripts/01_schema.sql
psql -d "$DB_NAME" -q -v ON_ERROR_STOP=1 -f scripts/02_seed.sql
psql -d "$DB_NAME" -q -v ON_ERROR_STOP=1 -v ro_password="$DB_PASSWORD" -f scripts/03_roles.sql
psql -d "$DB_NAME" -q -v ON_ERROR_STOP=1 -f scripts/04_demo_roles.sql
psql -d "$DB_NAME" -q -v ON_ERROR_STOP=1 -f scripts/05_schema_events.sql
psql -d "$DB_NAME" -qc "ANALYZE"
echo "Database $DB_NAME is ready."
