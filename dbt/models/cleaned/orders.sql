-- Cleaned orders: one row per order, latest version wins, deletes filtered out.
-- Dedup by _source_lsn (strict total order), NOT ts_ms.
WITH deduped AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY id ORDER BY _source_lsn DESC) AS rn
    FROM {{ source('raw', 'orders_raw') }}
    WHERE _op != 'd'
    {% if is_incremental() %}
      AND _source_lsn > (SELECT COALESCE(MAX(_source_lsn), 0) FROM {{ this }})
    {% endif %}
)
SELECT id,
       customer_id,
       status,
       CAST(total_cents AS DOUBLE) / 100.0 AS total_usd,
       created_at,
       _source_lsn,
       _event_ts AS last_updated
FROM deduped
WHERE rn = 1
