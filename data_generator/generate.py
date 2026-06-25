"""Synthetic e-commerce activity generator.

Drives the source Postgres DB with a steady stream of INSERT/UPDATE/DELETE
operations so the CDC pipeline always has fresh change events to capture.
Runs forever; one weighted random operation every 2 seconds (SPEC §11).
"""

import logging
import os
import random
import sys
import time

import psycopg2
from faker import Faker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("data_generator")

fake = Faker()

CITIES = ["Mumbai", "Delhi", "Bangalore", "Pune", "Chennai", "Hyderabad", "Kolkata", "Jaipur"]
STATUS_FLOW = {"pending": "processing", "processing": "shipped", "shipped": "delivered"}

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "postgres"),
    "port": os.getenv("POSTGRES_PORT", "5432"),
    "dbname": os.getenv("POSTGRES_DB", "shop"),
    "user": os.getenv("POSTGRES_USER", "admin"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
}


def connect():
    """Connect to Postgres, retrying for up to 30s on startup."""
    deadline = time.time() + 30
    while True:
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            log.info("Connected to Postgres at %s:%s", DB_CONFIG["host"], DB_CONFIG["port"])
            return conn
        except psycopg2.OperationalError as exc:
            if time.time() > deadline:
                raise
            log.info("Postgres not ready, retrying in 2s... (%s)", str(exc).strip())
            time.sleep(2)


def insert_customer(cur):
    name = fake.name()
    email = f"{fake.user_name()}.{random.randint(1000, 999999)}@example.com"
    city = random.choice(CITIES)
    cur.execute(
        "INSERT INTO customers (name, email, city) VALUES (%s, %s, %s) RETURNING id",
        (name, email, city),
    )
    cid = cur.fetchone()[0]
    log.info("INSERT customer id=%s name=%r city=%s", cid, name, city)


def insert_order(cur):
    cur.execute("SELECT id FROM customers ORDER BY random() LIMIT 1")
    row = cur.fetchone()
    if not row:
        return
    customer_id = row[0]
    cur.execute(
        "SELECT id, price_cents FROM products ORDER BY random() LIMIT %s",
        (random.randint(1, 3),),
    )
    chosen = [(pid, price, random.randint(1, 5)) for pid, price in cur.fetchall()]
    if not chosen:
        return
    total = sum(price * qty for _, price, qty in chosen)
    cur.execute(
        "INSERT INTO orders (customer_id, status, total_cents) VALUES (%s, 'pending', %s) RETURNING id",
        (customer_id, total),
    )
    order_id = cur.fetchone()[0]
    for product_id, price, qty in chosen:
        cur.execute(
            "INSERT INTO order_items (order_id, product_id, quantity, price_cents) "
            "VALUES (%s, %s, %s, %s)",
            (order_id, product_id, qty, price),
        )
    log.info(
        "INSERT order id=%s customer=%s items=%s total_cents=%s",
        order_id, customer_id, len(chosen), total,
    )


def update_order_status(cur):
    cur.execute("SELECT id, status FROM orders WHERE status <> 'delivered' ORDER BY random() LIMIT 1")
    row = cur.fetchone()
    if not row:
        return
    order_id, status = row
    nxt = STATUS_FLOW.get(status)
    if not nxt:
        return
    cur.execute("UPDATE orders SET status = %s, updated_at = now() WHERE id = %s", (nxt, order_id))
    log.info("UPDATE order id=%s status %s -> %s", order_id, status, nxt)


def update_customer_city(cur):
    cur.execute("SELECT id FROM customers ORDER BY random() LIMIT 1")
    row = cur.fetchone()
    if not row:
        return
    customer_id = row[0]
    city = random.choice(CITIES)
    cur.execute("UPDATE customers SET city = %s WHERE id = %s", (city, customer_id))
    log.info("UPDATE customer id=%s city=%s", customer_id, city)


def delete_pending_order(cur):
    """Cancel an old pending order (delete its items first to respect the FK)."""
    cur.execute("SELECT id FROM orders WHERE status = 'pending' ORDER BY created_at ASC LIMIT 1")
    row = cur.fetchone()
    if not row:
        return
    order_id = row[0]
    cur.execute("DELETE FROM order_items WHERE order_id = %s", (order_id,))
    cur.execute("DELETE FROM orders WHERE id = %s", (order_id,))
    log.info("DELETE order id=%s (simulated cancellation)", order_id)


# (operation, probability) — sums to 1.0 (SPEC §11)
ACTIONS = [
    (insert_customer, 0.20),
    (insert_order, 0.30),
    (update_order_status, 0.30),
    (update_customer_city, 0.10),
    (delete_pending_order, 0.10),
]
FNS = [fn for fn, _ in ACTIONS]
WEIGHTS = [w for _, w in ACTIONS]


# --- One-time historical backfill: ~30 days of backdated orders so the dashboard
#     charts / KPIs / "% delivered" look populated immediately. ---
BACKFILL_DAYS = 30


def _status_for_age(days_ago: int) -> str:
    """Older orders are mostly delivered; recent ones spread across the funnel."""
    if days_ago > 7:
        return random.choices(["delivered", "shipped", "processing"], weights=[85, 10, 5])[0]
    if days_ago > 2:
        return random.choices(
            ["delivered", "shipped", "processing", "pending"], weights=[50, 25, 15, 10]
        )[0]
    return random.choices(
        ["pending", "processing", "shipped", "delivered"], weights=[35, 25, 20, 20]
    )[0]


def backfill_history(conn, days: int = BACKFILL_DAYS):
    """Insert ~`days` of backdated orders once. Idempotent: skips if any order
    already predates the last 7 days (i.e. the backfill has already run)."""
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM orders WHERE created_at < now() - interval '7 days'")
        if cur.fetchone()[0] > 0:
            log.info("history backfill skipped — historical orders already present")
            return

        cur.execute("SELECT id, price_cents FROM products")
        products = cur.fetchall()
        cur.execute("SELECT id FROM customers")
        customer_ids = [r[0] for r in cur.fetchall()]
        if not products or not customer_ids:
            log.warning("history backfill skipped — no products/customers yet")
            return

        inserted = 0
        for days_ago in range(days, 0, -1):
            for _ in range(random.randint(15, 35)):
                # a random instant within that day, in the past
                offset = f"interval '{days_ago} days' - interval '{random.randint(0, 86399)} seconds'"
                customer_id = random.choice(customer_ids)
                items = [
                    (pid, price, random.randint(1, 5))
                    for pid, price in random.sample(products, random.randint(1, 3))
                ]
                total = sum(price * qty for _, price, qty in items)
                cur.execute(
                    "INSERT INTO orders (customer_id, status, total_cents, created_at, updated_at) "
                    f"VALUES (%s, %s, %s, now() - {offset}, now() - {offset}) RETURNING id",
                    (customer_id, _status_for_age(days_ago), total),
                )
                order_id = cur.fetchone()[0]
                for product_id, price, qty in items:
                    cur.execute(
                        "INSERT INTO order_items (order_id, product_id, quantity, price_cents) "
                        "VALUES (%s, %s, %s, %s)",
                        (order_id, product_id, qty, price),
                    )
                inserted += 1
        conn.commit()
        log.info("history backfill: inserted %d backdated orders across %d days", inserted, days)


def main():
    conn = connect()
    backfill_history(conn)
    log.info("Data generator started — one operation every 2s")
    while True:
        fn = random.choices(FNS, weights=WEIGHTS, k=1)[0]
        try:
            with conn.cursor() as cur:
                fn(cur)
            conn.commit()
        except psycopg2.OperationalError as exc:
            log.error("Lost connection (%s) — reconnecting", str(exc).strip())
            try:
                conn.close()
            except Exception:
                pass
            conn = connect()
        except Exception as exc:
            log.error("Operation %s failed: %s", fn.__name__, exc)
            conn.rollback()
        time.sleep(2)


if __name__ == "__main__":
    main()
