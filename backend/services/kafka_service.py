"""Background Kafka consumer feeding the Pipeline Monitor's live event stream.

Subscribes to all `shop.public.*` topics (group `pipeline-monitor`), keeps the last
200 CDC events in memory, and exposes a monotonic sequence so the WebSocket endpoint
can stream only new events. End-to-end-ish latency (source commit → observed) is
measured per event, never hardcoded (SPEC §7.10).
"""

import json
import threading
import time
from collections import deque
from datetime import datetime, timezone

from confluent_kafka import Consumer, KafkaError

from config import settings

_events = deque(maxlen=200)
_lock = threading.Lock()
_seq = 0
_stats = {
    "events_total": 0,
    "events_today": 0,
    "last_event_ms": None,
    "last_latency_ms": None,
    "_today": None,
}


def recent_events(n: int = 50):
    """Most recent events, newest first."""
    with _lock:
        return list(_events)[-n:][::-1]


def current_seq() -> int:
    with _lock:
        return _seq


def events_since(seq: int):
    """New events with sequence > seq, oldest first (for WS streaming)."""
    with _lock:
        return [e for e in _events if e["_seq"] > seq]


def get_stats() -> dict:
    with _lock:
        return {k: v for k, v in _stats.items() if not k.startswith("_")}


def _record(topic: str, payload: dict):
    global _seq
    source_ts_ms = payload.get("__source_ts_ms")
    now_ms = int(time.time() * 1000)
    latency = (now_ms - int(source_ts_ms)) if source_ts_ms is not None else None
    today = datetime.now(timezone.utc).date().isoformat()

    with _lock:
        _seq += 1
        event = {
            "_seq": _seq,
            "table": topic.split(".")[-1],
            "op": payload.get("__op"),
            "topic": topic,
            "source_ts_ms": source_ts_ms,
            "received_ms": now_ms,
            "latency_ms": latency,
            "data": {k: v for k, v in payload.items() if not k.startswith("__")},
        }
        _events.append(event)
        _stats["events_total"] += 1
        if _stats["_today"] != today:
            _stats["_today"] = today
            _stats["events_today"] = 0
        _stats["events_today"] += 1
        _stats["last_event_ms"] = now_ms
        _stats["last_latency_ms"] = latency


def _consume_loop():
    consumer = Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap,
            "group.id": "pipeline-monitor",
            "auto.offset.reset": "latest",
            "enable.auto.commit": True,
        }
    )
    consumer.subscribe([r"^shop\.public\..*"])
    while True:
        try:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() != KafkaError._PARTITION_EOF:
                    time.sleep(1)
                continue
            if not msg.value():
                continue
            payload = json.loads(msg.value())
            _record(msg.topic(), payload)
        except Exception:
            time.sleep(1)  # never let the monitor consumer die


def start_consumer():
    threading.Thread(target=_consume_loop, daemon=True, name="kafka-monitor").start()
