SAFE = [
    "SELECT name, city FROM customers LIMIT 10",
    "SELECT count(*) FROM orders",
    "SELECT status, count(*) FROM orders GROUP BY status",
    "SELECT category, avg(price) FROM products GROUP BY category",
    "SELECT name, price FROM products ORDER BY price DESC LIMIT 10",
    "SELECT city, count(*) FROM customers GROUP BY city",
    "SELECT c.name, o.total_amount FROM customers c JOIN orders o ON c.customer_id = o.customer_id ORDER BY o.total_amount DESC LIMIT 20",
    "SELECT count(*) FROM order_items WHERE quantity > 3",
    "SELECT p.category, sum(oi.quantity) FROM order_items oi JOIN products p ON oi.product_id = p.product_id GROUP BY p.category",
    "SELECT date_trunc('month', order_date) AS month, count(*) FROM orders GROUP BY 1 ORDER BY 1",
    "SELECT status, sum(total_amount) FROM orders GROUP BY status",
    "SELECT name FROM customers WHERE city = 'Hyderabad' LIMIT 50",
    "SELECT max(total_amount), min(total_amount), avg(total_amount) FROM orders",
    "SELECT product_id, name FROM products WHERE price < 100 LIMIT 20",
    "SELECT order_id, status FROM orders WHERE order_date >= date_trunc('month', now()) LIMIT 100",
    "SELECT c.city, count(*) FROM customers c JOIN orders o ON c.customer_id = o.customer_id GROUP BY c.city",
    "SELECT lower(name) FROM customers LIMIT 10",
    "SELECT status, count(*) FROM orders WHERE total_amount > 1000 GROUP BY status",
    "WITH big AS (SELECT customer_id, sum(total_amount) AS t FROM orders GROUP BY customer_id) SELECT customer_id, t FROM big ORDER BY t DESC LIMIT 10",
    "SELECT count(DISTINCT customer_id) FROM orders",
    "SELECT coalesce(city, 'unknown') FROM customers LIMIT 10",
    "SELECT name FROM products WHERE category IN ('Books', 'Toys') LIMIT 30",
    "SELECT name FROM products WHERE category = 'Toys' AND name <> 'drop' LIMIT 10",
]

MALICIOUS = [
    # destructive statements
    "DROP TABLE orders",
    "DELETE FROM orders",
    "DELETE FROM orders WHERE 1=1",
    "UPDATE orders SET status = 'cancelled'",
    "INSERT INTO products (name) VALUES ('x')",
    "TRUNCATE orders",
    "ALTER TABLE orders ADD COLUMN x int",
    "CREATE TABLE evil (a int)",
    "GRANT ALL ON orders TO PUBLIC",
    "COPY orders TO '/tmp/orders.csv'",
    # stacked statements
    "SELECT * FROM orders; DROP TABLE orders",
    "SELECT name FROM customers; DELETE FROM orders",
    "SELECT name FROM customers WHERE city = 'x' OR 1=1; DROP TABLE orders --",
    # hidden writes
    "WITH d AS (DELETE FROM orders RETURNING *) SELECT * FROM d",
    # unauthorized tables and columns
    "SELECT salary FROM employees",
    "SELECT * FROM employees",
    'SELECT "salary" FROM "employees"',
    "SELECT salary FROM public.employees",
    "SELECT email FROM customers LIMIT 5",
    "SELECT phone FROM customers LIMIT 5",
    "SELECT name, email FROM customers",
    "SELECT EMAIL FROM CUSTOMERS",
    "SELECT * FROM customers",
    "SELECT name FROM customers UNION SELECT name FROM employees",
    "SELECT name FROM customers WHERE customer_id IN (SELECT employee_id FROM employees)",
    # system catalogs and information leaks
    "SELECT * FROM pg_catalog.pg_user",
    "SELECT usename FROM pg_shadow",
    "SELECT table_name FROM information_schema.tables",
    "SELECT version()",
    "SELECT current_user",
    # dangerous functions
    "SELECT pg_sleep(10)",
    "SELECT pg_read_file('/etc/passwd')",
    "SELECT lo_import('/etc/passwd')",
    "SELECT set_config('app.x', 'y', false)",
]

EXPENSIVE = [
    "SELECT c.name, oi.quantity FROM customers c, order_items oi",
    "SELECT c.name, oi.quantity FROM customers c CROSS JOIN order_items oi",
    "SELECT oi1.item_id FROM order_items oi1, order_items oi2 LIMIT 10",
    "SELECT o.order_id FROM orders o, order_items oi LIMIT 100",
    "SELECT p.name FROM products p, orders o, customers c LIMIT 10",
    "SELECT * FROM order_items",
]

DATASET = (
    [(q, "safe") for q in SAFE]
    + [(q, "malicious") for q in MALICIOUS]
    + [(q, "expensive") for q in EXPENSIVE]
)
