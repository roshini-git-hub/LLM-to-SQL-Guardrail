CREATE TABLE customers (
    customer_id SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL,
    phone       TEXT,
    city        TEXT,
    created_at  TIMESTAMP DEFAULT now()
);

CREATE TABLE products (
    product_id SERIAL PRIMARY KEY,
    name       TEXT NOT NULL,
    category   TEXT,
    price      NUMERIC(10,2)
);

CREATE TABLE orders (
    order_id     SERIAL PRIMARY KEY,
    customer_id  INT REFERENCES customers(customer_id),
    order_date   TIMESTAMP,
    status       TEXT,
    total_amount NUMERIC(10,2)
);

CREATE TABLE order_items (
    item_id    SERIAL PRIMARY KEY,
    order_id   INT REFERENCES orders(order_id),
    product_id INT REFERENCES products(product_id),
    quantity   INT,
    unit_price NUMERIC(10,2)
);

CREATE TABLE employees (
    employee_id SERIAL PRIMARY KEY,
    name        TEXT,
    department  TEXT,
    salary      NUMERIC(10,2)
);