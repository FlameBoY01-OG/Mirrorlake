"""Thin Trino query helper. Returns JSON-serializable result dicts."""

import time

import trino

from config import settings


def _cell(value):
    """Coerce a Trino cell to something JSON-serializable."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def get_connection():
    return trino.dbapi.connect(
        host=settings.trino_host,
        port=settings.trino_port,
        user=settings.trino_user,
        catalog=settings.trino_catalog,
        schema=settings.trino_schema,
        session_properties={"query_max_run_time": "30s"},
    )


def run_query(sql: str) -> dict:
    """Run SQL on Trino; never raises — errors come back in the `error` field."""
    start = time.time()
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(sql)
        raw_rows = cur.fetchall()
        columns = [d[0] for d in cur.description] if cur.description else []
        rows = [[_cell(c) for c in row] for row in raw_rows]
        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "duration_ms": int((time.time() - start) * 1000),
            "error": None,
        }
    except Exception as exc:
        return {
            "columns": [],
            "rows": [],
            "row_count": 0,
            "duration_ms": int((time.time() - start) * 1000),
            "error": str(exc),
        }
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
