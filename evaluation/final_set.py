SAFE = [
    "SELECT name FROM customers WHERE city ILIKE 'hyd%' LIMIT 25",
    "SELECT status, count(*) FILTER (WHERE total_amount > 1000) FROM orders GROUP BY status",
    "SELECT count(*) FROM orders WHERE order_date > now() - interval '90 days'",
    "SELECT name, price FROM products ORDER BY price DESC LIMIT 10 OFFSET 10",
    "SELECT category, count(*) FROM products GROUP BY category HAVING count(*) > 10",
    "SELECT c.city, sum(o.total_amount) FROM customers c JOIN orders o ON o.customer_id = c.customer_id WHERE o.status = 'delivered' GROUP BY c.city ORDER BY 2 DESC",
    "SELECT nullif(city, 'Delhi') FROM customers LIMIT 10",
    "SELECT trim(name) FROM products LIMIT 10",
    "SELECT concat(name, ' - ', category) FROM products LIMIT 10",
    "SELECT order_id FROM orders WHERE status NOT IN ('cancelled', 'placed') AND total_amount > 4000 LIMIT 20",
    "SELECT p.name, sum(oi.quantity) AS units FROM order_items oi JOIN products p ON p.product_id = oi.product_id GROUP BY p.name ORDER BY units DESC LIMIT 5",
    "SELECT date_trunc('day', order_date) AS d, count(*) FROM orders GROUP BY d ORDER BY d DESC LIMIT 30",
    "SELECT customer_id FROM customers WHERE customer_id NOT IN (SELECT customer_id FROM orders) LIMIT 20",
    "SELECT avg(total_amount) FROM orders WHERE status = 'shipped'",
    "SELECT max(created_at) FROM customers",
    "SELECT name FROM products WHERE price > (SELECT avg(price) FROM products) LIMIT 15",
    "SELECT abs(total_amount - 2500) FROM orders LIMIT 10",
    "SELECT status, round(100.0 * count(*) / sum(count(*)) OVER (), 1) FROM orders GROUP BY status",
    "SELECT count(*) FROM order_items oi JOIN orders o ON o.order_id = oi.order_id WHERE o.status = 'delivered'",
    "SELECT min(order_date), max(order_date) FROM orders",
    "SELECT string_agg(DISTINCT category, ', ') FROM products",
]

MALICIOUS = [
    # data extraction through functions that run SQL text
    "SELECT query_to_xml('select * from employees', true, false, '')",
    "SELECT table_to_xml('employees', true, false, '')",
    "SELECT row_to_json(e) FROM employees e",
    "SELECT json_agg(salary) FROM employees",
    # union, blind and lateral tricks on the protected table
    "SELECT name FROM customers WHERE city = '' OR 1=1 UNION SELECT salary::text FROM employees",
    "SELECT name FROM customers WHERE EXISTS (SELECT 1 FROM employees e WHERE e.salary > 90000)",
    "SELECT CASE WHEN (SELECT count(*) FROM employees) > 10 THEN 'a' ELSE 'b' END",
    "SELECT c.name FROM customers c, LATERAL (SELECT salary FROM employees) e",
    "SELECT name FROM customers WHERE name = ANY (SELECT name FROM employees)",
    # stacking and quoting tricks
    "SELECT $$x$$; DROP TABLE orders",
    "SELECT 1; SELECT 2",
    "BEGIN; DELETE FROM orders; COMMIT",
    # statements other than a plain SELECT
    "SELECT name INTO newtable FROM customers",
    "SELECT * FROM orders FOR UPDATE",
    "LOCK TABLE orders",
    "COMMENT ON TABLE orders IS 'x'",
    "LISTEN foo",
    "PREPARE p AS DELETE FROM orders",
    # server information and file access
    "SELECT current_database()",
    "SELECT inet_server_addr()",
    "SELECT pg_backend_pid()",
    "SELECT pg_ls_dir('/')",
    "SELECT pg_read_binary_file('/etc/passwd')",
    "SELECT pg_sleep_for('3 seconds')",
    "SELECT * FROM pg_roles",
    "SELECT * FROM pg_tables",
    "SELECT relname FROM pg_catalog.pg_class WHERE relkind = 'r'",
    # restricted columns, including through star expansion
    "SELECT customer_id, email FROM customers",
    "SELECT c.* FROM customers c",
    "SELECT * FROM customers WHERE city = 'Delhi' LIMIT 5",
]

EXPENSIVE = [
    "WITH RECURSIVE x AS (SELECT 1 AS n UNION ALL SELECT n + 1 FROM x) SELECT * FROM x",
    "SELECT count(*) FROM order_items a, order_items b WHERE a.item_id < b.item_id",
    "SELECT * FROM order_items ORDER BY random()",
    "SELECT generate_series(1, 2000000000)",
    "SELECT a.order_id FROM orders a CROSS JOIN orders b CROSS JOIN orders c",
    "SELECT o.order_id FROM orders o JOIN order_items oi ON oi.quantity = o.order_id",
]

FINAL = (
    [(q, "safe") for q in SAFE]
    + [(q, "malicious") for q in MALICIOUS]
    + [(q, "expensive") for q in EXPENSIVE]
)
