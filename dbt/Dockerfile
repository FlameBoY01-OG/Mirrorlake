FROM python:3.11-slim

WORKDIR /dbt

RUN pip install --no-cache-dir "dbt-trino==1.8.1"

COPY . /dbt

ENV DBT_PROFILES_DIR=/dbt

# Default to a full build (run + test). Override per invocation, e.g.
#   docker compose run --rm dbt build
CMD ["dbt", "build"]
