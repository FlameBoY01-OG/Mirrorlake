-- Revenue and order counts per customer city.
SELECT c.city,
       COUNT(o.id)       AS orders,
       SUM(o.total_usd)  AS revenue_usd
FROM {{ ref('orders') }} o
JOIN {{ ref('customers') }} c ON o.customer_id = c.id
WHERE c.city IS NOT NULL
GROUP BY c.city
ORDER BY revenue_usd DESC
