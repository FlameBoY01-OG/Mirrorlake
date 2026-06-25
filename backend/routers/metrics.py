"""Read-only metrics endpoints for the Executive Dashboard (SPEC §16, §18)."""

from fastapi import APIRouter

from services import trino_service

router = APIRouter()


@router.get("/metrics/revenue")
def revenue():
    return trino_service.run_query(
        "SELECT * FROM iceberg.shop.daily_revenue ORDER BY date DESC LIMIT 30"
    )


@router.get("/metrics/funnel")
def funnel():
    return trino_service.run_query("SELECT * FROM iceberg.shop.order_funnel")


@router.get("/metrics/top-customers")
def top_customers():
    return trino_service.run_query(
        "SELECT * FROM iceberg.shop.customer_ltv ORDER BY lifetime_value_usd DESC LIMIT 10"
    )


@router.get("/metrics/top-products")
def top_products():
    return trino_service.run_query(
        "SELECT * FROM iceberg.shop.top_products ORDER BY revenue_usd DESC LIMIT 10"
    )


@router.get("/metrics/revenue-by-city")
def revenue_by_city():
    return trino_service.run_query(
        "SELECT * FROM iceberg.shop.revenue_by_city ORDER BY revenue_usd DESC LIMIT 10"
    )


# --- Live metrics -----------------------------------------------------------
# Computed directly from the raw layer (deduped by LSN) so they update as new CDC
# data lands — no dbt run required. This is what makes the dashboard real-time.

def _dicts(res):
    return [dict(zip(res["columns"], r)) for r in res["rows"]] if not res["error"] else []


def _one(res):
    rows = _dicts(res)
    return rows[0] if rows else {}


# Current state of every order: latest version per id, deletes removed. `b` carries
# "now" as a naive-UTC timestamp so it compares cleanly to the stored created_at.
_LIVE_ORDERS = """
WITH ranked AS (
    SELECT id, customer_id, status,
           CAST(total_cents AS DOUBLE) / 100.0 AS total_usd, created_at,
           ROW_NUMBER() OVER (PARTITION BY id ORDER BY _source_lsn DESC) AS rn
    FROM iceberg.shop.orders_raw
    WHERE _op <> 'd'
),
live_orders AS (SELECT * FROM ranked WHERE rn = 1),
b AS (SELECT CAST(current_timestamp AT TIME ZONE 'UTC' AS timestamp(6)) AS now_utc)
"""

# Date-range windows as SQL expressions over b.now_utc: (current_start, previous_start).
# The previous window is [previous_start, current_start) — same length as the current one.
_RANGES = {
    "today": ("date_trunc('day', b.now_utc)", "date_trunc('day', b.now_utc) - interval '1' day"),
    "7d": ("b.now_utc - interval '7' day", "b.now_utc - interval '14' day"),
    "30d": ("b.now_utc - interval '30' day", "b.now_utc - interval '60' day"),
    "all": ("timestamp '1970-01-01 00:00:00'", None),
}


def _pct(cur, prev):
    if prev in (0, None) or cur is None:
        return None
    return round((float(cur) - float(prev)) / float(prev) * 100, 1)


@router.get("/metrics/live")
def live(range: str = "30d"):
    """Real-time metrics for the selected date range, with period-over-period deltas.

    range ∈ {today, 7d, 30d, all}. Everything is computed live from the raw layer.
    """
    if range not in _RANGES:
        range = "30d"
    cur_start, prev_start = _RANGES[range]
    in_cur = f"o.created_at >= {cur_start}"
    in_prev = f"(o.created_at >= {prev_start} AND o.created_at < {cur_start})" if prev_start else "false"

    k = _one(trino_service.run_query(_LIVE_ORDERS + f"""
        SELECT
          COALESCE(sum(CASE WHEN {in_cur} THEN o.total_usd END), 0)                         AS revenue_usd,
          count(CASE WHEN {in_cur} THEN 1 END)                                              AS total_orders,
          COALESCE(avg(CASE WHEN {in_cur} THEN o.total_usd END), 0)                         AS avg_order_value,
          COALESCE(sum(CASE WHEN {in_cur} AND o.status='delivered' THEN o.total_usd END),0) AS delivered_revenue,
          count(CASE WHEN {in_cur} AND o.status='delivered' THEN 1 END)                     AS delivered_orders,
          count(DISTINCT CASE WHEN {in_cur} THEN o.customer_id END)                         AS buying_customers,
          COALESCE(sum(CASE WHEN {in_prev} THEN o.total_usd END), 0)                        AS prev_revenue,
          count(CASE WHEN {in_prev} THEN 1 END)                                             AS prev_orders,
          COALESCE(avg(CASE WHEN {in_prev} THEN o.total_usd END), 0)                        AS prev_aov
        FROM live_orders o, b
    """))
    customers = _one(trino_service.run_query("""
        SELECT count(*) AS active_customers FROM (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY id ORDER BY _source_lsn DESC) AS rn
            FROM iceberg.shop.customers_raw WHERE _op <> 'd'
        ) t WHERE rn = 1
    """))
    by_status = _dicts(trino_service.run_query(_LIVE_ORDERS + f"""
        SELECT o.status, count(*) AS orders, COALESCE(sum(o.total_usd), 0) AS revenue
        FROM live_orders o, b WHERE {in_cur} GROUP BY o.status
    """))
    revenue_by_day = _dicts(trino_service.run_query(_LIVE_ORDERS + f"""
        SELECT CAST(DATE(o.created_at) AS VARCHAR) AS date,
               count(*) AS orders, COALESCE(sum(o.total_usd), 0) AS revenue
        FROM live_orders o, b WHERE {in_cur} GROUP BY DATE(o.created_at) ORDER BY 1
    """))
    recent_orders = _dicts(trino_service.run_query(_LIVE_ORDERS + f"""
        SELECT o.id, o.status, o.total_usd AS amount, CAST(o.created_at AS VARCHAR) AS created_at
        FROM live_orders o, b WHERE {in_cur} ORDER BY o.created_at DESC LIMIT 40
    """))

    return {
        "range": range,
        "kpis": {
            "revenue_usd": k.get("revenue_usd", 0),
            "total_orders": k.get("total_orders", 0),
            "avg_order_value": k.get("avg_order_value", 0),
            "delivered_revenue": k.get("delivered_revenue", 0),
            "delivered_orders": k.get("delivered_orders", 0),
            "buying_customers": k.get("buying_customers", 0),
            "active_customers": customers.get("active_customers", 0),
        },
        "deltas": {
            "revenue_usd": _pct(k.get("revenue_usd"), k.get("prev_revenue")),
            "total_orders": _pct(k.get("total_orders"), k.get("prev_orders")),
            "avg_order_value": _pct(k.get("avg_order_value"), k.get("prev_aov")),
        },
        "by_status": by_status,
        "revenue_by_day": revenue_by_day,
        "recent_orders": recent_orders,
    }
