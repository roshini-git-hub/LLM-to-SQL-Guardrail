-- Demo roles: the guardrail's behaviour changes with these GRANTs, COMMENTs and RLS
-- policies alone. No Python code knows about any of them.
--   psql -d guardrail_db -f scripts/04_demo_roles.sql   (run as the database owner)

-- 1. Roles (NOLOGIN: the guardrail's login role switches to them with SET ROLE)
CREATE ROLE analyst NOLOGIN;
CREATE ROLE city_manager NOLOGIN;
CREATE ROLE support NOLOGIN;
GRANT USAGE ON SCHEMA public TO analyst, city_manager, support;
-- guardrail_ro may switch to these roles (SET ROLE) but does NOT inherit their privileges,
-- otherwise the default role would silently gain support's access to email/phone.
GRANT analyst, city_manager, support TO guardrail_ro WITH INHERIT FALSE, SET TRUE;

-- 2. analyst: sales data, customers without contact details
GRANT SELECT ON products, orders, order_items TO analyst;
GRANT SELECT (customer_id, name, city, created_at) ON customers TO analyst;

-- 3. city_manager: same columns as analyst, but only rows for one city (RLS below)
GRANT SELECT ON products, orders, order_items TO city_manager;
GRANT SELECT (customer_id, name, city, created_at) ON customers TO city_manager;

-- 4. support: may see contact details (PII) but not money columns or products
GRANT SELECT (customer_id, name, email, phone, city) ON customers TO support;
GRANT SELECT (order_id, customer_id, order_date, status) ON orders TO support;

-- 5. Mark sensitive columns. The guardrail reads these comments from the catalog.
COMMENT ON COLUMN customers.email IS 'PII: customer contact email';
COMMENT ON COLUMN customers.phone IS 'PII: customer phone number';
COMMENT ON COLUMN employees.salary IS 'sensitive: payroll';

-- 6. Row-Level Security. Once RLS is enabled, a role with no matching policy sees no rows,
--    so every other role gets an explicit "all rows" policy.
ALTER TABLE customers   ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders      ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_items ENABLE ROW LEVEL SECURITY;

CREATE POLICY all_rows ON customers   FOR SELECT TO guardrail_ro, analyst, support USING (true);
CREATE POLICY all_rows ON orders      FOR SELECT TO guardrail_ro, analyst, support USING (true);
CREATE POLICY all_rows ON order_items FOR SELECT TO guardrail_ro, analyst, support USING (true);

CREATE POLICY one_city ON customers FOR SELECT TO city_manager
    USING (city = 'Hyderabad');
-- Subqueries inside a policy are themselves filtered by RLS, so these chain to Hyderabad.
CREATE POLICY one_city ON orders FOR SELECT TO city_manager
    USING (customer_id IN (SELECT customer_id FROM customers));
CREATE POLICY one_city ON order_items FOR SELECT TO city_manager
    USING (order_id IN (SELECT order_id FROM orders));
