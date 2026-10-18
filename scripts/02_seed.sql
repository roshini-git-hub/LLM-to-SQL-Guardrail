INSERT INTO customers (name, email, phone, city)
SELECT 'Customer ' || g,
       'user' || g || '@example.com',
       '9' || lpad((random()*999999999)::int::text, 9, '0'),
       (ARRAY['Hyderabad','Chennai','Mumbai','Delhi','Bengaluru'])[1 + floor(random()*5)::int]
FROM generate_series(1, 10000) g;

INSERT INTO products (name, category, price)
SELECT 'Product ' || g,
       (ARRAY['Books','Electronics','Clothing','Home','Toys'])[1 + floor(random()*5)::int],
       round((random()*990 + 10)::numeric, 2)
FROM generate_series(1, 200) g;

INSERT INTO orders (customer_id, order_date, status, total_amount)
SELECT 1 + floor(random()*10000)::int,
       now() - random() * interval '730 days',
       (ARRAY['placed','shipped','delivered','cancelled'])[1 + floor(random()*4)::int],
       round((random()*5000)::numeric, 2)
FROM generate_series(1, 200000);

INSERT INTO order_items (order_id, product_id, quantity, unit_price)
SELECT 1 + floor(random()*200000)::int,
       1 + floor(random()*200)::int,
       1 + floor(random()*5)::int,
       round((random()*990 + 10)::numeric, 2)
FROM generate_series(1, 600000);

INSERT INTO employees (name, department, salary)
SELECT 'Employee ' || g,
       (ARRAY['HR','Sales','Engineering','Finance'])[1 + floor(random()*4)::int],
       round((30000 + random()*90000)::numeric, 2)
FROM generate_series(1, 50) g;

ANALYZE;