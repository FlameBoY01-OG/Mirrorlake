-- Orders per status for the funnel chart (pending → processing → shipped → delivered).
SELECT status,
       COUNT(*)        AS order_count,
       SUM(total_usd)  AS revenue_usd
FROM {{ ref('orders') }}
GROUP BY status
ORDER BY CASE status
           WHEN 'pending'    THEN 1
           WHEN 'processing' THEN 2
           WHEN 'shipped'    THEN 3
           WHEN 'delivered'  THEN 4
           ELSE 5
         END
