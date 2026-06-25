CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE customers (
    id         SERIAL PRIMARY KEY,
    name       TEXT NOT NULL,
    email      TEXT UNIQUE NOT NULL,
    city       TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE products (
    id          SERIAL PRIMARY KEY,
    sku         TEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL,
    category    TEXT,
    price_cents INT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE orders (
    id          SERIAL PRIMARY KEY,
    customer_id INT REFERENCES customers(id),
    status      TEXT DEFAULT 'pending',
    total_cents INT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE order_items (
    id          SERIAL PRIMARY KEY,
    order_id    INT REFERENCES orders(id),
    product_id  INT REFERENCES products(id),
    quantity    INT NOT NULL,
    price_cents INT NOT NULL
);

SELECT pg_create_logical_replication_slot('debezium_slot', 'pgoutput')
WHERE NOT EXISTS (SELECT 1 FROM pg_replication_slots WHERE slot_name = 'debezium_slot');

INSERT INTO customers (name, email, city)
SELECT 'Customer ' || i, 'user' || i || '@example.com',
       (ARRAY['Mumbai','Delhi','Bangalore','Pune','Chennai'])[1 + (i % 5)]
FROM generate_series(1, 100) i;

INSERT INTO products (sku, name, category, price_cents) VALUES
('PHONE-001','Smartphone X','Electronics',49999),
('LAPTOP-001','Laptop Pro 15','Electronics',89999),
('SHIRT-001','Cotton T-Shirt','Clothing',999),
('BOOK-001','Python Cookbook','Books',1499),
('HEADPH-001','Wireless Headphones','Electronics',7999),
('JEANS-001','Slim Fit Jeans','Clothing',2499),
('WATCH-001','Smart Watch','Electronics',14999),
('BAG-001','Laptop Backpack','Accessories',3499);
