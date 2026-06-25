"""Create the Iceberg raw-layer tables before the consumer loop (SPEC §13, §22.3).

Idempotent: namespace + tables are created only if absent, so this is safe to run
on every container start. Each raw table = the source columns PLUS CDC metadata
(`_op`, `_event_ts`, `_source_ts`, `_source_lsn`, `_deleted`) and is partitioned by
day on `_source_ts`.
"""

import logging
import os
import sys

from pyiceberg.catalog import load_catalog
from pyiceberg.exceptions import TableAlreadyExistsError
from pyiceberg.partitioning import PartitionField, PartitionSpec
from pyiceberg.schema import Schema
from pyiceberg.transforms import DayTransform
from pyiceberg.types import (
    BooleanType,
    LongType,
    NestedField,
    StringType,
    TimestampType,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("setup_tables")

NAMESPACE = "shop"

# Source columns per raw table, in order (mirrors postgres/init.sql).
SOURCE_COLUMNS = {
    "customers_raw": [
        ("id", LongType()),
        ("name", StringType()),
        ("email", StringType()),
        ("city", StringType()),
        ("created_at", TimestampType()),
    ],
    "products_raw": [
        ("id", LongType()),
        ("sku", StringType()),
        ("name", StringType()),
        ("category", StringType()),
        ("price_cents", LongType()),
        ("created_at", TimestampType()),
    ],
    "orders_raw": [
        ("id", LongType()),
        ("customer_id", LongType()),
        ("status", StringType()),
        ("total_cents", LongType()),
        ("created_at", TimestampType()),
        ("updated_at", TimestampType()),
    ],
    "order_items_raw": [
        ("id", LongType()),
        ("order_id", LongType()),
        ("product_id", LongType()),
        ("quantity", LongType()),
        ("price_cents", LongType()),
    ],
}

# CDC metadata appended to every raw table (SPEC §13).
META_COLUMNS = [
    ("_op", StringType()),
    ("_event_ts", TimestampType()),
    ("_source_ts", TimestampType()),
    ("_source_lsn", LongType()),
    ("_deleted", BooleanType()),
]


def columns_for(table: str):
    """Full ordered column list (source + metadata) for a raw table."""
    return SOURCE_COLUMNS[table] + META_COLUMNS


def build_schema(columns) -> Schema:
    fields = [
        NestedField(field_id=i, name=name, field_type=ftype, required=False)
        for i, (name, ftype) in enumerate(columns, start=1)
    ]
    return Schema(*fields)


def get_catalog():
    return load_catalog(
        "rest",
        **{
            "uri": os.environ["ICEBERG_REST_URL"],
            "s3.endpoint": os.environ["MINIO_ENDPOINT"],
            "s3.access-key-id": os.environ["MINIO_ROOT_USER"],
            "s3.secret-access-key": os.environ["MINIO_ROOT_PASSWORD"],
            "s3.path-style-access": "true",
            "s3.region": os.environ.get("AWS_REGION", "us-east-1"),
        },
    )


def main():
    catalog = get_catalog()
    catalog.create_namespace_if_not_exists(NAMESPACE)
    log.info("namespace %r ready", NAMESPACE)

    for table in SOURCE_COLUMNS:
        identifier = f"{NAMESPACE}.{table}"
        schema = build_schema(columns_for(table))
        source_ts_id = schema.find_field("_source_ts").field_id
        partition_spec = PartitionSpec(
            PartitionField(
                source_id=source_ts_id,
                field_id=1000,
                transform=DayTransform(),
                name="_source_ts_day",
            )
        )
        # Idempotent: catch the race/exists case directly rather than relying on a
        # separate table_exists() probe (which the REST catalog can report stale).
        try:
            catalog.create_table(identifier=identifier, schema=schema, partition_spec=partition_spec)
            log.info("created table %s (partitioned by day(_source_ts))", identifier)
        except TableAlreadyExistsError:
            log.info("table %s already exists — skipping", identifier)

    log.info("setup_tables complete")


if __name__ == "__main__":
    main()
