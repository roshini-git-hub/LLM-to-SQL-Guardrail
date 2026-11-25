-- Run with the password passed in from the environment (never hard-coded here):
--   psql -d guardrail_db -v ro_password="$DB_PASSWORD" -f scripts/03_roles.sql
-- or use scripts/setup_db.sh which does this for you.

CREATE ROLE guardrail_ro LOGIN PASSWORD :'ro_password';

GRANT CONNECT ON DATABASE guardrail_db TO guardrail_ro;
GRANT USAGE ON SCHEMA public TO guardrail_ro;

GRANT SELECT ON products, orders, order_items TO guardrail_ro;
GRANT SELECT (customer_id, name, city, created_at) ON customers TO guardrail_ro;

ALTER ROLE guardrail_ro SET statement_timeout = '5s';
ALTER ROLE guardrail_ro SET default_transaction_read_only = on;
