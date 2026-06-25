-- Top products by revenue: dedup raw order_items + products by LSN, then aggregate.
WITH items AS (
    SELECT order_id, product_id, quantity, price_cents,
           ROW_NUMBER() OVER (PARTITION BY id ORDER BY _source_lsn DESC) AS rn
    FROM {{ source('raw', 'order_items_raw') }}
    WHERE _op != 'd'
),
prods AS (
    SELECT id, name, category,
           ROW_NUMBER() OVER (PARTITION BY id ORDER BY _source_lsn DESC) AS rn
    FROM {{ source('raw', 'products_raw') }}
    WHERE _op != 'd'
)
SELECT p.id                                       AS product_id,
       p.name                                     AS product_name,
       p.category                                 AS category,
       SUM(i.quantity)                            AS units_sold,
       SUM(i.quantity * i.price_cents) / 100.0    AS revenue_usd
FROM items i
JOIN prods p ON i.product_id = p.id AND p.rn = 1
WHERE i.rn = 1
GROUP BY p.id, p.name, p.category
ORDER BY revenue_usd DESC
