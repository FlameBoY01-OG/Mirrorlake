-- Cleaned customers: one row per customer, latest version wins, deletes filtered.
WITH deduped AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY id ORDER BY _source_lsn DESC) AS rn
    FROM {{ source('raw', 'customers_raw') }}
    WHERE _op != 'd'
    {% if is_incremental() %}
      AND _source_lsn > (SELECT COALESCE(MAX(_source_lsn), 0) FROM {{ this }})
    {% endif %}
)
SELECT id,
       name,
       email,
       city,
       created_at,
       _source_lsn,
       _event_ts AS last_updated
FROM deduped
WHERE rn = 1
