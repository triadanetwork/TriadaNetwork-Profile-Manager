import json
import logging
import os
import time
import uuid
from contextvars import ContextVar
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import Counter, Gauge, Histogram

REQUEST_ID: ContextVar[str] = ContextVar("triada_request_id", default="-")

HTTP_REQUESTS = Counter(
    "triada_http_requests_total",
    "Total HTTP requests handled by the cloud control plane.",
    ["method", "route", "status"],
)
HTTP_DURATION = Histogram(
    "triada_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
HTTP_IN_FLIGHT = Gauge("triada_http_in_flight", "HTTP requests currently in flight.")
APP_ERRORS = Counter("triada_app_errors_total", "Unhandled application errors.", ["exception"])
RATE_LIMIT_ERRORS = Counter("triada_rate_limit_errors_total", "Rate-limit service errors.")
HEALTH_CHECKS = Counter("triada_health_checks_total", "Health checks executed.", ["check", "status"])
READY = Gauge("triada_ready", "Whether the cloud control plane is ready (1=yes, 0=no).")


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    level = os.getenv("TRIADA_CLOUD_LOG_LEVEL", "INFO").upper()
    root.setLevel(getattr(logging, level, logging.INFO))


def log_event(level: int, event: str, **fields: object) -> None:
    payload = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "level": logging.getLevelName(level),
        "service": "triada-cloud",
        "environment": os.getenv("TRIADA_CLOUD_ENVIRONMENT", "development"),
        "event": event,
        "request_id": REQUEST_ID.get(),
        **fields,
    }
    logging.getLogger("triada.cloud").log(level, json.dumps(payload, separators=(",", ":"), default=str))


def _route_label(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", request.url.path) or request.url.path


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        token = REQUEST_ID.set(request_id)
        started = time.perf_counter()
        HTTP_IN_FLIGHT.inc()
        try:
            response = await call_next(request)
        except Exception as exc:
            APP_ERRORS.labels(type(exc).__name__).inc()
            log_event(
                logging.ERROR,
                "http.request.error",
                method=request.method,
                path=request.url.path,
                exception=type(exc).__name__,
                error=str(exc),
            )
            raise
        finally:
            HTTP_IN_FLIGHT.dec()
            REQUEST_ID.reset(token)

        elapsed = time.perf_counter() - started
        route = _route_label(request)
        HTTP_REQUESTS.labels(request.method, route, str(response.status_code)).inc()
        HTTP_DURATION.labels(request.method, route).observe(elapsed)
        response.headers["X-Request-ID"] = request_id
        log_event(
            logging.INFO,
            "http.request",
            method=request.method,
            path=request.url.path,
            route=route,
            status=response.status_code,
            duration_ms=round(elapsed * 1000, 2),
        )
        return response
