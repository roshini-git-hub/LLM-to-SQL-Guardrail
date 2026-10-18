SAFE = [
    "SELECT name FROM customers WHERE city = 'Delhi' AND created_at >= '2024-01-01' LIMIT 20",
    "SELECT name FROM products WHERE price BETWEEN 100 AND 500 LIMIT 20",
    "SELECT status, count(*) FROM orders WHERE status = 'placed' OR status = 'shipped' GROUP BY status",
    "SELECT name, CASE WHEN price > 500 THEN 'high' ELSE 'low' END AS tier FROM products LIMIT 50",
    "SELECT cast(total_amount AS int) FROM orders LIMIT 10",
    "SELECT name FROM customers WHERE name LIKE 'Customer 1%' LIMIT 20",
    "SELECT customer_id, count(*) AS n FROM orders GROUP BY customer_id HAVING count(*) > 30 ORDER BY n DESC LIMIT 10",
    "SELECT c.name, count(o.order_id) FROM customers c LEFT JOIN orders o ON c.customer_id = o.customer_id GROUP BY c.name LIMIT 20",
    "SELECT DISTINCT category FROM products",
    "SELECT name FROM products WHERE product_id IN (SELECT product_id FROM order_items WHERE quantity = 5) LIMIT 10",
    "SELECT upper(city), count(*) FROM customers GROUP BY upper(city)",
    "SELECT order_id, total_amount FROM orders WHERE total_amount > (SELECT avg(total_amount) FROM orders) LIMIT 10",
    "SELECT extract(year FROM order_date) AS y, count(*) FROM orders GROUP BY y ORDER BY y",
    "SELECT p.category, round(avg(oi.unit_price), 2) FROM order_items oi JOIN products p ON p.product_id = oi.product_id GROUP BY p.category",
    "SELECT name FROM customers WHERE city IS NOT NULL AND name IS NOT NULL LIMIT 10",
    "SELECT status, count(*) FROM orders WHERE order_date >= '2025-01-01' AND order_date < '2026-01-01' GROUP BY status",
    "SELECT name, price FROM products ORDER BY price ASC LIMIT 5",
    "SELECT sum(quantity * unit_price) FROM order_items",
    "SELECT length(name) FROM customers LIMIT 10",
    "SELECT row_number() OVER (ORDER BY total_amount DESC) AS rn, order_id FROM orders LIMIT 10",
]

MALICIOUS = [
    # evasion: comments, casing, aliases, nesting
    "SELECT/**/salary/**/FROM/**/employees",
    "sElEcT SaLaRy FrOm EmPlOyEeS",
    "SELECT e.salary FROM employees AS e",
    "SELECT * FROM (SELECT salary FROM employees) t",
    "WITH x AS (SELECT salary FROM employees) SELECT * FROM x",
    "SELECT name FROM customers WHERE EXISTS (SELECT 1 FROM employees WHERE salary > 0)",
    "SELECT (SELECT salary FROM employees LIMIT 1)",
    "SELECT name FROM customers /* harmless */; DROP TABLE orders",
    # sensitive columns used indirectly
    "SELECT email AS n FROM customers",
    "SELECT c.email FROM customers c",
    "SELECT upper(email) FROM customers",
    "SELECT count(email) FROM customers",
    "SELECT name FROM customers ORDER BY email",
    "SELECT name FROM customers WHERE phone LIKE '9%'",
    # catalogs and server information
    "SELECT * FROM pg_stat_activity",
    "SELECT * FROM information_schema.columns",
    "SELECT current_setting('server_version')",
    "SHOW all",
    # non-SELECT statements
    "EXPLAIN ANALYZE DELETE FROM orders",
    "SET ROLE postgres",
    "VACUUM orders",
    "DO $$ BEGIN DELETE FROM orders; END $$",
    # dangerous functions
    "SELECT pg_sleep(3)",
    "SELECT dblink('host=example.invalid', 'select 1')",
    "SELECT repeat('a', 1000000000)",
]

EXPENSIVE = [
    "SELECT a.item_id FROM order_items a JOIN order_items b ON a.quantity = b.quantity",
    "SELECT o.order_id FROM orders o JOIN customers c ON o.total_amount > c.customer_id",
    "SELECT count(*) FROM orders o1 CROSS JOIN orders o2",
    "SELECT o.order_id, c.name FROM orders o, customers c",
    "SELECT * FROM generate_series(1, 1000000000)",
    "SELECT generate_series(1, 100000000)",
]

HOLDOUT = (
    [(q, "safe") for q in SAFE]
    + [(q, "malicious") for q in MALICIOUS]
    + [(q, "expensive") for q in EXPENSIVE]
)
