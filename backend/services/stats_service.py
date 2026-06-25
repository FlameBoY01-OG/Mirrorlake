"""Health checks for every service + real pipeline stats (SPEC §16).

All checks are defensive: a down dependency yields a `down` status, never a 500.
"""

import time

import psycopg2
import requests
from confluent_kafka.admin import AdminClient

from config import settings
from services import debezium_service, kafka_service, trino_service

RAW_TABLES = ["orders_raw", "customers_raw", "order_items_raw", "products_raw"]


def _check_postgres() -> dict:
    try:
        conn = psycopg2.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            dbname=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password,
            connect_timeout=5,
        )
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        conn.close()
        return {"status": "up"}
    except Exception as exc:
        return {"status": "down", "detail": str(exc)}


def _http_check(url: str) -> dict:
    try:
        r = requests.get(url, timeout=5)
        return {"status": "up" if r.ok else "degraded", "code": r.status_code}
    except Exception as exc:
        return {"status": "down", "detail": str(exc)}


def _check_kafka() -> dict:
    try:
        md = AdminClient({"bootstrap.servers": settings.kafka_bootstrap}).list_topics(timeout=5)
        return {"status": "up", "topics": len(md.topics)}
    except Exception as exc:
        return {"status": "down", "detail": str(exc)}


def _check_trino() -> dict:
    res = trino_service.run_query("SELECT 1")
    return {"status": "up" if res["error"] is None else "down", "detail": res["error"]}


def _measure_latency_ms():
    """End-to-end latency: now − newest source-commit time landed in the raw layer."""
    res = trino_service.run_query("SELECT to_unixtime(max(_source_ts)) FROM iceberg.shop.orders_raw")
    if res["error"] or not res["rows"] or res["rows"][0][0] is None:
        return None
    return int(time.time() * 1000 - float(res["rows"][0][0]) * 1000)


def _snapshot_count():
    total = 0
    any_ok = False
    for t in RAW_TABLES:
        res = trino_service.run_query(f'SELECT count(*) FROM iceberg.shop."{t}$snapshots"')
        if res["error"] is None and res["rows"]:
            any_ok = True
            total += int(res["rows"][0][0])
    return total if any_ok else None


def _last_dbt_run():
    from routers import dbt_runner  # lazy import to avoid an import cycle

    st = dbt_runner.current_state()
    return {"status": st.get("status"), "finished_at": st.get("finished_at")}


def build_stats() -> dict:
    ev = kafka_service.get_stats()
    return {
        "end_to_end_latency_ms": _measure_latency_ms(),
        "events_today": ev.get("events_today", 0),
        "events_total": ev.get("events_total", 0),
        "snapshot_count": _snapshot_count(),
        "last_dbt_run": _last_dbt_run(),
    }


def health() -> dict:
    services = {
        "postgres": _check_postgres(),
        "kafka": _check_kafka(),
        "kafka_connect": _http_check(f"{settings.kafka_connect_url}/connectors"),
        "debezium": debezium_service.connector_status(),
        "iceberg": _http_check(f"{settings.iceberg_rest_url}/v1/config"),
        "minio": _http_check(f"{settings.minio_endpoint}/minio/health/live"),
        "trino": _check_trino(),
    }
    overall = "healthy" if all(s["status"] == "up" for s in services.values()) else "degraded"
    return {"status": overall, "services": services, "stats": build_stats()}
