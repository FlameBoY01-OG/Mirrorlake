"""Debezium / Kafka Connect connector status via the Connect REST API."""

import requests

from config import settings


def connector_status() -> dict:
    url = f"{settings.kafka_connect_url}/connectors/{settings.connector_name}/status"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 404:
            return {"status": "down", "detail": "connector not registered"}
        r.raise_for_status()
        data = r.json()
        state = data.get("connector", {}).get("state", "UNKNOWN")
        task_states = [t.get("state") for t in data.get("tasks", [])]
        healthy = state == "RUNNING" and all(s == "RUNNING" for s in task_states or ["RUNNING"])
        return {
            "status": "up" if healthy else "degraded",
            "state": state,
            "tasks": task_states,
        }
    except Exception as exc:
        return {"status": "down", "detail": str(exc)}
