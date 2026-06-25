SELECT DATE(created_at)                                   AS date,
       COUNT(*)                                          AS order_count,
       SUM(total_usd)                                    AS revenue_usd,
       AVG(total_usd)                                    AS avg_order_value,
       COUNT(DISTINCT customer_id)                       AS unique_customers,
       COUNT(CASE WHEN status = 'delivered' THEN 1 END)  AS delivered_orders
FROM {{ ref('orders') }}
GROUP BY DATE(created_at)
ORDER BY date DESC
