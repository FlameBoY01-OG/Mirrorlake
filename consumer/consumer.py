"""Idempotent Kafka -> Iceberg raw-layer consumer (SPEC §7.3, §13).

Reads the Debezium CDC topics (`shop.public.*`), buffers events per table, and
flushes each batch as a single atomic Iceberg snapshot. Kafka offsets are committed
ONLY AFTER the Iceberg snapshot commit succeeds, so a crash mid-batch is replayed on
restart and de-duplicated downstream in the cleaned layer by `_source_lsn` (never double-counted).

Unparseable messages are routed to a `dlq` topic instead of crashing the loop.
"""

import json
import logging
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

import pyarrow as pa
from confluent_kafka import Consumer, KafkaError, Producer
from pyiceberg.io.pyarrow import schema_to_pyarrow

from setup_tables import NAMESPACE, columns_for, get_catalog

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("consumer")

# Flush thresholds (SPEC §7.3): 100 events OR every 30s.
FLUSH_COUNT = int(os.getenv("FLUSH_COUNT", "100"))
FLUSH_SECONDS = int(os.getenv("FLUSH_SECONDS", "30"))
DLQ_TOPIC = "dlq"

BOOTSTRAP = os.environ["KAFKA_BOOTSTRAP_INTERNAL"]
TOPIC_PATTERN = r"^shop\.public\..*"

# Debezium topic `shop.public.<table>` -> Iceberg raw table.
TABLE_MAP = {
    "shop.public.customers": "customers_raw",
    "shop.public.products": "products_raw",
    "shop.public.orders": "orders_raw",
    "shop.public.order_items": "order_items_raw",
}
# Source columns that arrive as ISO-8601 timestamp strings (TIMESTAMPTZ in Postgres).
TS_SOURCE_COLUMNS = {"created_at", "updated_at"}


def parse_source_ts(val):
    """Parse a Debezium source timestamp (ISO-8601 string, or epoch micros) -> naive UTC."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return datetime.fromtimestamp(val / 1_000_000, tz=timezone.utc).replace(tzinfo=None)
    dt = datetime.fromisoformat(str(val).replace("Z", "+00:00"))
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def ms_to_dt(ms):
    if ms is None:
        return None
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).replace(tzinfo=None)


def to_record(raw_table: str, payload: dict) -> dict:
    """Map a Debezium unwrapped JSON payload to a row matching the Iceberg schema."""
    record = {}
    for name, _ftype in columns_for(raw_table):
        if name.startswith("_"):
            continue  # metadata, filled in below
        val = payload.get(name)
        if name in TS_SOURCE_COLUMNS:
            val = parse_source_ts(val)
        record[name] = val

    op = payload.get("__op")
    lsn = payload.get("__source_lsn")
    source_ts = ms_to_dt(payload.get("__source_ts_ms"))
    event_ts = ms_to_dt(payload.get("__ts_ms"))

    record["_op"] = op
    record["_event_ts"] = event_ts
    # Partitioning needs a non-null _source_ts; fall back to event time, then now.
    record["_source_ts"] = source_ts or event_ts or datetime.now(timezone.utc).replace(tzinfo=None)
    record["_source_lsn"] = int(lsn) if lsn is not None else None
    record["_deleted"] = payload.get("__deleted") == "true" or op == "d"
    return record


class IcebergSink:
    """Buffers rows per table and flushes them as atomic Iceberg snapshots."""

    def __init__(self):
        self.catalog = get_catalog()
        self.buffers = defaultdict(list)
        self._arrow_schemas = {}

    def add(self, raw_table: str, record: dict):
        self.buffers[raw_table].append(record)

    @property
    def buffered(self) -> int:
        return sum(len(v) for v in self.buffers.values())

    def _arrow_schema(self, raw_table: str):
        if raw_table not in self._arrow_schemas:
            table = self.catalog.load_table(f"{NAMESPACE}.{raw_table}")
            self._arrow_schemas[raw_table] = schema_to_pyarrow(table.schema())
        return self._arrow_schemas[raw_table]

    def flush(self):
        """Append every buffered batch to Iceberg. Raises if any commit fails."""
        for raw_table, rows in list(self.buffers.items()):
            if not rows:
                continue
            table = self.catalog.load_table(f"{NAMESPACE}.{raw_table}")
            arrow_table = pa.Table.from_pylist(rows, schema=self._arrow_schema(raw_table))
            table.append(arrow_table)  # atomic Iceberg snapshot commit
            log.info("Flushed %d events to iceberg.%s.%s", len(rows), NAMESPACE, raw_table)
            self.buffers[raw_table].clear()


def main():
    consumer = Consumer(
        {
            "bootstrap.servers": BOOTSTRAP,
            "group.id": "iceberg-consumer",
            "enable.auto.commit": False,  # SPEC §7.3 — manual commit after Iceberg snapshot
            "auto.offset.reset": "earliest",
            # Rediscover regex-matched topics every 10s, so a consumer that started
            # before the connector created shop.public.* picks them up automatically
            # (no manual restart needed). librdkafka default is 5 minutes.
            "topic.metadata.refresh.interval.ms": 10000,
            "allow.auto.create.topics": False,
        }
    )
    consumer.subscribe([TOPIC_PATTERN])
    dlq = Producer({"bootstrap.servers": BOOTSTRAP})
    sink = IcebergSink()
    last_flush = time.time()

    log.info("consumer started — bootstrap=%s pattern=%s", BOOTSTRAP, TOPIC_PATTERN)

    def maybe_flush(force=False):
        nonlocal last_flush
        due = sink.buffered >= FLUSH_COUNT or (time.time() - last_flush) >= FLUSH_SECONDS
        if sink.buffered > 0 and (force or due):
            try:
                sink.flush()
            except Exception as exc:  # keep buffer, retry next loop — do NOT commit offsets
                log.error("Iceberg flush failed, will retry (offsets NOT committed): %s", exc)
                return
            consumer.commit(asynchronous=False)  # only after the snapshot committed
            last_flush = time.time()

    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                maybe_flush()
                continue
            if msg.error():
                if msg.error().code() != KafkaError._PARTITION_EOF:
                    log.error("consumer error: %s", msg.error())
                continue

            topic = msg.topic()
            raw_table = TABLE_MAP.get(topic)
            try:
                if raw_table is None:
                    raise ValueError(f"no raw table mapped for topic {topic}")
                if msg.value() is None:
                    continue  # tombstone (kept disabled, but be safe)
                payload = json.loads(msg.value())
                sink.add(raw_table, to_record(raw_table, payload))
            except Exception as exc:
                log.warning("routing message to DLQ (%s): %s", topic, exc)
                dlq.produce(DLQ_TOPIC, value=msg.value(), key=msg.key())
                dlq.poll(0)

            maybe_flush()
    except KeyboardInterrupt:
        log.info("shutting down — final flush")
    finally:
        try:
            maybe_flush(force=True)
        finally:
            dlq.flush(5)
            consumer.close()


if __name__ == "__main__":
    main()
