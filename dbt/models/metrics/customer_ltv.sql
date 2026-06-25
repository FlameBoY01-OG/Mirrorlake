SELECT c.id,
       c.name,
       c.email,
       c.city,
       COUNT(o.id)         AS total_orders,
       SUM(o.total_usd)    AS lifetime_value_usd,
       AVG(o.total_usd)    AS avg_order_value,
       MAX(o.created_at)   AS last_order_at
FROM {{ ref('customers') }} c
LEFT JOIN {{ ref('orders') }} o ON c.id = o.customer_id
WHERE o.status = 'delivered'
GROUP BY c.id, c.name, c.email, c.city
ORDER BY lifetime_value_usd DESC
