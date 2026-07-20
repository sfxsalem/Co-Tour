"""Vendor-neutral request observability for the Co-Tour web adapter."""

from __future__ import annotations

import json
import logging
import re
import sys
import traceback
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from fastapi import Request


REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{7,127}$")
request_logger = logging.getLogger("cotour.requests")


def configure_request_logger() -> None:
    """Emit one JSON object per line without taking over application logging."""
    if request_logger.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    request_logger.addHandler(handler)
    request_logger.setLevel(logging.INFO)
    request_logger.propagate = False


def correlation_id(request: Request) -> str:
    supplied = request.headers.get("X-Request-ID", "")
    if REQUEST_ID_PATTERN.fullmatch(supplied):
        return supplied
    return str(uuid4())


def route_pattern(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", "__unmatched__")


def request_event(
    request: Request,
    *,
    request_id: str,
    status_code: int,
    started_at: float,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "timestamp": datetime.now(UTC).isoformat(),
        "event": "http_request",
        "service": "cotour-web",
        "request_id": request_id,
        "method": request.method,
        "route": route_pattern(request),
        "status_code": status_code,
        "duration_ms": round((perf_counter() - started_at) * 1000, 3),
    }


def log_request(event: dict[str, object], *, failed: bool = False) -> None:
    payload = json.dumps(event, separators=(",", ":"), sort_keys=True)
    if failed:
        request_logger.error(payload)
    else:
        request_logger.info(payload)


def exception_fields(exc: Exception) -> dict[str, object]:
    """Keep diagnostic stack locations without logging exception messages or locals."""
    frames = traceback.extract_tb(exc.__traceback__)[-12:]
    return {
        "error_type": type(exc).__name__,
        "stack": [
            {"file": frame.filename, "function": frame.name, "line": frame.lineno}
            for frame in frames
        ],
    }
