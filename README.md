# Mirrorlake

A real-time **Change Data Capture (CDC) lakehouse pipeline**. It watches a PostgreSQL
e-commerce database for every `INSERT` / `UPDATE` / `DELETE` and streams those changes
into a separate analytical lakehouse in near real-time — so analytics never touch the
live production database. This mirrors the pattern used by companies like Uber, Airbnb,
and LinkedIn.

A single `docker compose up` brings up the whole stack: the pipeline, the dbt transforms,
a FastAPI backend, and two React UIs.

---

## Architecture

```
PostgreSQL (source DB)
   │  WAL  (logical replication)
   ▼
Debezium  (CDC connector in Kafka Connect)
   ▼
Apache Kafka  (KRaft mode — no Zookeeper)          one topic per table: shop.public.*
   ▼
Python Iceberg Consumer  (idempotent, exactly-once-ish)
   │  commits Kafka offsets ONLY after the Iceberg snapshot commits
   ▼
Apache Iceberg on MinIO  (S3-compatible lakehouse storage)
   ▼
dbt  (raw → cleaned → metrics)
   ▼
Trino  (distributed SQL engine over Iceberg)
   ▼
FastAPI backend ──► Pipeline Monitor (engineers)  +  Executive Dashboard (the boss)
```

The data moves through three layers:

- **raw** — CDC events exactly as captured, append-only audit log (incl. deletes as `_op='d'`).
- **cleaned** — deduplicated by Postgres LSN (latest wins), deletes filtered out (one row per order/customer).
- **metrics** — pre-aggregated business numbers (daily revenue, customer LTV, order funnel).

---

## Tech stack

PostgreSQL 15 · Debezium 2.7 · Kafka 7.5 (KRaft) · Schema Registry · MinIO ·
Iceberg REST catalog · Trino 426 · Python 3.11 (confluent-kafka, PyIceberg) ·
dbt-trino · FastAPI · React 18 + Vite + TypeScript + Tailwind + Recharts.

---

## Prerequisites

Just **Docker** (with Docker Compose v2). Nothing else needs to be installed on the host.

---

## Quick start

Run these **in order**, from the project folder. Prerequisite: Docker only.

```bash
# 1. Create your local config file (one time).
cp .env.example .env

# 2. Start the WHOLE app in the background. This single command starts every
#    service: database, Kafka, MinIO, Trino, the backend API, BOTH web UIs, AND
#    the demo data simulation. There is NO separate command for the backend or
#    frontends — they all start here.
docker compose up -d --build

# 3. Wait ~60 seconds for things to boot, then connect Debezium to Postgres.
#    (Required — without this, no change-data is captured. See note below.)
bash debezium/register_connector.sh

# 4. (Optional) Build the dbt analytics tables used by the Pipeline Monitor and
#    the /metrics/revenue|funnel|top-customers endpoints.
docker compose --profile jobs run --rm dbt dbt build
```

**Then open these in your web browser:**

| Open in browser            | What you get                       |
|----------------------------|------------------------------------|
| http://localhost:5174      | **Executive Dashboard** (boss UI)  |
| http://localhost:5173      | **Pipeline Monitor** (engineer UI) |
| http://localhost:8000/docs | **Backend API** (interactive docs) |

**Stop everything when you're done:**

```bash
docker compose down        # stop the app (keeps your data)
docker compose down -v     # stop AND wipe all data, for a clean restart
```

### About the "demo simulation" (it starts automatically)

There is **no command to start the simulation** — the `data-generator` service is
part of the stack, so `docker compose up` (step 2) starts it for you. It:

- on first start, **backfills ~30 days of historical orders** so the charts and KPIs
  look populated immediately, then
- runs forever, continuously doing realistic INSERT / UPDATE / DELETE operations on
  the Postgres database (~one every 2 seconds).

Those database changes are what flow through the pipeline and show up live in both
UIs. You don't start it, stop it, or call it separately.

### Why step 3 (Debezium) is separate

`docker compose up` only *starts* the services. Debezium (the change-capture tool)
can only be told what to watch **after** Kafka Connect is healthy, so registering it
is a separate one-line command. If the Executive Dashboard is empty, it's almost
always because step 3 wasn't run, or the app was restarted with stale data — in that
case do a clean restart: `docker compose down -v` then repeat steps 2–3.

### Service URLs

| Service              | URL                          |
|----------------------|------------------------------|
| Pipeline Monitor UI  | http://localhost:5173        |
| Executive Dashboard  | http://localhost:5174        |
| Backend API          | http://localhost:8000        |
| Trino                | http://localhost:8080        |
| MinIO console        | http://localhost:9001        |
| Kafka Connect REST   | http://localhost:8083        |

### Running the backend and the two frontends

These come up automatically as part of `docker compose up` — there is **no separate
command** to start them. All three are volume-mounted and **hot-reload** on code changes.

| Component             | URL                   | Rebuild / restart just this service               |
|-----------------------|-----------------------|---------------------------------------------------|
| Backend (FastAPI)     | http://localhost:8000 | `docker compose up -d --build backend`            |
| Pipeline Monitor (UI) | http://localhost:5173 | `docker compose up -d --build frontend-monitor`   |
| Executive Dashboard   | http://localhost:5174 | `docker compose up -d --build frontend-exec`      |

```bash
# tail their logs
docker compose logs -f backend
docker compose logs -f frontend-monitor frontend-exec
```

Once the stack is up, open **http://localhost:5173** (engineers) and
**http://localhost:5174** (executives) in your browser.

**Run a frontend outside Docker** (optional, for UI work):

```bash
cd frontend-monitor        # or frontend-exec
npm install
npm run dev                # serves on 5173 (monitor) / 5174 (exec)
# point it at the containerized backend if needed:
VITE_API_URL=http://localhost:8000 npm run dev
```

---

## Demo — end-to-end in ~10 seconds

```bash
bash scripts/demo.sh
```

This inserts a new customer into Postgres and confirms it reaches the backend's live
event stream within a few seconds. You can also watch it live on the **Live Events**
tab of the Pipeline Monitor, then hit **Run dbt now** on the **dbt Controls** tab and
see the new numbers on the Executive Dashboard.

---

## Useful commands

```bash
docker compose ps                                   # service status
docker compose logs -f backend                      # tail a service
docker compose --profile jobs run --rm dbt dbt build  # run dbt
bash debezium/register_connector.sh                 # (re)register the connector (idempotent)
docker compose down                                 # stop everything
docker compose down -v                              # stop + wipe all data volumes
```

---

## Project layout

```
docker-compose.yml          # the whole stack
postgres/init.sql           # source schema + logical replication slot
data_generator/             # synthetic INSERT/UPDATE/DELETE traffic
debezium/                   # register_connector.sh
consumer/                   # idempotent Kafka → Iceberg raw-layer writer
dbt/                        # raw (source) → cleaned → metrics + tests
trino/                      # Trino catalog + config
backend/                    # FastAPI: /health /events /query /dbt/* /metrics/*
frontend-monitor/           # engineer UI (4 screens)
frontend-exec/              # boss UI (read-only KPIs + charts)
```

---

## Notes

- Containers talk to each other by **service name** (`kafka:9092`, `trino:8080`), not
  `localhost`. Host tools use the mapped ports above.
- The consumer commits Kafka offsets **only after** the Iceberg snapshot commits, so it
  is safe to restart without duplicating data; the cleaned layer deduplicates by LSN regardless.
- The Iceberg REST catalog does not support views, so the dbt cleaned models are materialized
  as tables (LSN-dedup keeps this idempotent).
