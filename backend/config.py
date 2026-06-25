"""Backend configuration, all sourced from environment (.env). No hardcoded secrets."""

import os


class Settings:
    # Postgres
    postgres_host = os.getenv("POSTGRES_HOST", "postgres")
    postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))
    postgres_db = os.getenv("POSTGRES_DB", "shop")
    postgres_user = os.getenv("POSTGRES_USER", "admin")
    postgres_password = os.getenv("POSTGRES_PASSWORD", "")

    # Kafka / Connect / Debezium
    kafka_bootstrap = os.getenv("KAFKA_BOOTSTRAP_INTERNAL", "kafka:9092")
    kafka_connect_url = os.getenv("KAFKA_CONNECT_URL", "http://kafka-connect:8083")
    connector_name = os.getenv("CONNECTOR_NAME", "postgres-cdc-connector")

    # MinIO / Iceberg
    minio_endpoint = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
    iceberg_rest_url = os.getenv("ICEBERG_REST_URL", "http://iceberg-rest:8181")

    # Trino
    trino_host = os.getenv("TRINO_HOST", "trino")
    trino_port = int(os.getenv("TRINO_PORT", "8080"))
    trino_user = os.getenv("TRINO_USER", "admin")
    trino_catalog = "iceberg"
    trino_schema = "shop"

    # dbt
    dbt_project_dir = os.getenv("DBT_PROJECT_DIR", "/dbt")

    # API
    backend_port = int(os.getenv("BACKEND_PORT", "8000"))
    cors_origins = [
        o.strip()
        for o in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://localhost:5174"
        ).split(",")
        if o.strip()
    ]


settings = Settings()
