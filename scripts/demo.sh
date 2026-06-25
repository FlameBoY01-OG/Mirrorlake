#!/usr/bin/env bash
# Demo: insert a new customer into Postgres and watch it reach the backend's live
# event stream — the end-to-end Definition of Done.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set -a
[ -f "$ROOT_DIR/.env" ] && . "$ROOT_DIR/.env"
set +a

PG_USER="${POSTGRES_USER:-admin}"
PG_DB="${POSTGRES_DB:-shop}"
MARK="DEMO_$(date +%s)"

echo "Inserting customer '$MARK' into Postgres..."
docker exec cdc_postgres psql -U "$PG_USER" -d "$PG_DB" -c \
  "INSERT INTO customers (name, email, city) VALUES ('$MARK', '$MARK@demo.com', 'Mumbai');"

echo "Watching backend /events for it..."
for _ in $(seq 1 8); do
  if curl -s http://localhost:8000/events | grep -q "$MARK"; then
    echo "✅ '$MARK' reached the live CDC event stream."
    echo "   See it on the Pipeline Monitor: http://localhost:5173 (Live Events)"
    exit 0
  fi
  sleep 2
done

echo "⚠️  Not seen within ~16s. Check that the connector is registered:"
echo "    bash debezium/register_connector.sh"
exit 1
