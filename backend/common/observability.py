import json
import logging
import threading
import time
import uuid
from collections import defaultdict
from copy import deepcopy
from datetime import datetime


LOGGER_NAME = "smart_erp.observability"

_logger = logging.getLogger(LOGGER_NAME)
_lock = threading.Lock()
_metrics = defaultdict(int)
_timings = defaultdict(lambda: {"count": 0, "total_ms": 0.0, "max_ms": 0.0})


def utcnow_iso():
    return datetime.utcnow().isoformat() + "Z"


def generate_request_id():
    return uuid.uuid4().hex


def _metric_key(name, tags=None):
    if not tags:
        return name
    parts = [f"{key}={tags[key]}" for key in sorted(tags)]
    return f"{name}|{'|'.join(parts)}"


def increment_metric(name, value=1, tags=None):
    with _lock:
        _metrics[_metric_key(name, tags)] += value


def observe_timing(name, duration_ms, tags=None):
    with _lock:
        bucket = _timings[_metric_key(name, tags)]
        bucket["count"] += 1
        bucket["total_ms"] += float(duration_ms)
        bucket["max_ms"] = max(bucket["max_ms"], float(duration_ms))


def metrics_snapshot():
    with _lock:
        counters = dict(_metrics)
        timings = deepcopy(_timings)
    for key, bucket in timings.items():
        bucket["avg_ms"] = round(bucket["total_ms"] / bucket["count"], 2) if bucket["count"] else 0.0
        bucket["total_ms"] = round(bucket["total_ms"], 2)
        bucket["max_ms"] = round(bucket["max_ms"], 2)
    return {
        "generated_at": utcnow_iso(),
        "counters": counters,
        "timings": timings,
    }


def reset_metrics():
    with _lock:
        _metrics.clear()
        _timings.clear()


def log_event(event_type, level="info", **fields):
    payload = {"event": event_type, "timestamp": utcnow_iso(), **fields}
    message = json.dumps(payload, ensure_ascii=True, default=str)
    getattr(_logger, level.lower(), _logger.info)(message)


class ObservedOperation:
    def __init__(self, name, request_id=None, **context):
        self.name = name
        self.request_id = request_id or generate_request_id()
        self.context = context
        self.started_at = None

    def __enter__(self):
        self.started_at = time.perf_counter()
        log_event(f"{self.name}.started", request_id=self.request_id, **self.context)
        increment_metric("operation_started_total", tags={"operation": self.name})
        return self

    def success(self, **fields):
        duration_ms = (time.perf_counter() - self.started_at) * 1000 if self.started_at else 0
        observe_timing("operation_duration_ms", duration_ms, tags={"operation": self.name, "outcome": "success"})
        increment_metric("operation_success_total", tags={"operation": self.name})
        log_event(
            f"{self.name}.succeeded",
            request_id=self.request_id,
            duration_ms=round(duration_ms, 2),
            **self.context,
            **fields,
        )

    def failure(self, error_type, error_code, **fields):
        duration_ms = (time.perf_counter() - self.started_at) * 1000 if self.started_at else 0
        observe_timing("operation_duration_ms", duration_ms, tags={"operation": self.name, "outcome": error_type})
        increment_metric(
            "operation_failure_total",
            tags={"operation": self.name, "error_type": error_type, "error_code": error_code},
        )
        log_event(
            f"{self.name}.failed",
            level="warning" if error_type == "functional" else "error",
            request_id=self.request_id,
            duration_ms=round(duration_ms, 2),
            error_type=error_type,
            error_code=error_code,
            **self.context,
            **fields,
        )

    def __exit__(self, exc_type, exc, tb):
        return False
