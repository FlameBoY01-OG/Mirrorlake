#!/usr/bin/env bash
# Register (or update) the Debezium Postgres CDC connector.
# Idempotent: uses the PUT /connectors/<name>/config endpoint, so re-running
# updates the existing connector instead of failing.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Load credentials from .env (POSTGRES_USER / POSTGRES_PASSWORD)
set -a
[ -f "$ROOT_DIR/.env" ] && . "$ROOT_DIR/.env"
set +a

CONNECT_URL="${CONNECT_URL:-http://localhost:8083}"
CONNECTOR_NAME="postgres-cdc-connector"

echo "Waiting for Kafka Connect at ${CONNECT_URL} ..."
for _ in $(seq 1 60); do
  if curl -fsS "${CONNECT_URL}/connectors" >/dev/null 2>&1; then
    echo "Kafka Connect is ready."
    break
  fi
  sleep 3
done

echo "Registering ${CONNECTOR_NAME} ..."
curl -fsS -X PUT \
  -H "Content-Type: application/json" \
  "${CONNECT_URL}/connectors/${CONNECTOR_NAME}/config" \
  -d @- <<JSON
{
  "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
  "database.hostname": "postgres",
  "database.port": "5432",
  "database.user": "${POSTGRES_USER}",
  "database.password": "${POSTGRES_PASSWORD}",
  "database.dbname": "${POSTGRES_DB}",
  "topic.prefix": "shop",
  "table.include.list": "public.customers,public.orders,public.order_items,public.products",
  "plugin.name": "pgoutput",
  "slot.name": "debezium_slot",
  "publication.auto.create.mode": "filtered",
  "key.converter": "org.apache.kafka.connect.json.JsonConverter",
  "value.converter": "org.apache.kafka.connect.json.JsonConverter",
  "key.converter.schemas.enable": "false",
  "value.converter.schemas.enable": "false",
  "transforms": "unwrap",
  "transforms.unwrap.type": "io.debezium.transforms.ExtractNewRecordState",
  "transforms.unwrap.drop.tombstones": "false",
  "transforms.unwrap.delete.handling.mode": "rewrite",
  "transforms.unwrap.add.fields": "op,ts_ms,source.ts_ms,source.lsn",
  "heartbeat.interval.ms": "5000"
}
JSON

echo
echo "Connector status:"
curl -fsS "${CONNECT_URL}/connectors/${CONNECTOR_NAME}/status" || true
echo
