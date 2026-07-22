"""Observability seam (OBS lane): structured JSON logging, a request-id/context middleware, and
Sentry/OTel init hooks.

Log context (request id, user id, run id, stage) rides on contextvars so any log call in the
request/pipeline path carries it without threading the ids through every signature. The request
middleware binds request/user ids per HTTP request; `log_context(...)` binds run/user ids around
a pipeline run; each pipeline stage tags its own line with `stage`.

Sentry/OTel are init-only this milestone (no live DSN/exporter — deferred with hosting); the
hooks are here so a later milestone has one place to attach a backend.
"""

import json
import logging
import sys
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from uuid import UUID

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from specula_api.auth import decode_service_jwt
from specula_api.config import Settings

# Per-request / per-run context. Default None so a log emitted outside any context is still valid.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)
run_id_var: ContextVar[str | None] = ContextVar("run_id", default=None)
stage_var: ContextVar[str | None] = ContextVar("stage", default=None)

_CONTEXT_VARS = {
    "request_id": request_id_var,
    "user_id": user_id_var,
    "run_id": run_id_var,
    "stage": stage_var,
}

# Standard LogRecord attributes, computed from a sample so it tracks the running Python. Anything
# on a record NOT in here (nor a context field) is treated as an `extra=` field and serialized.
_RESERVED = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    *_CONTEXT_VARS,
}


class ContextFilter(logging.Filter):
    """Copies the current context vars onto each record (only if not already set, so an explicit
    `extra=` such as a pipeline stage tag wins)."""

    def filter(self, record: logging.LogRecord) -> bool:
        for name, var in _CONTEXT_VARS.items():
            if not hasattr(record, name):
                setattr(record, name, var.get())
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line: standard fields, the four context fields (null when unset), and
    any `extra=` fields the call passed."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
            "user_id": getattr(record, "user_id", None),
            "run_id": getattr(record, "run_id", None),
            "stage": getattr(record, "stage", None),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class _SpeculaHandler(logging.StreamHandler):  # type: ignore[type-arg]
    """Marker subclass so `configure_logging` can stay idempotent (detect its own handler)."""


def configure_logging(settings: Settings) -> None:
    """Attach a single JSON stdout handler to the `specula` logger namespace. Idempotent; scoped
    to `specula.*` (propagate=False) so it never reformats other libraries' or pytest's logging."""
    logger = logging.getLogger("specula")
    logger.setLevel(settings.log_level.upper())
    logger.propagate = False
    # Alembic's `fileConfig(disable_existing_loggers=True)` (run on migrate) disables every
    # logger that already existed — including `specula` AND its children (e.g. `specula.http`,
    # created at import). isEnabledFor checks each logger's own `disabled`, so re-enable the
    # whole subtree defensively, ahead of the handler early-return, before serving requests.
    for name, entry in [("specula", logger), *logging.root.manager.loggerDict.items()]:
        if isinstance(entry, logging.Logger) and (name == "specula" or name.startswith("specula.")):
            entry.disabled = False
    if any(isinstance(handler, _SpeculaHandler) for handler in logger.handlers):
        return
    handler = _SpeculaHandler(sys.stdout)
    handler.addFilter(ContextFilter())
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """A logger under the `specula.` namespace (e.g. get_logger("pipeline.extract"))."""
    return logging.getLogger(f"specula.{name}")


@contextmanager
def log_context(
    *,
    user_id: str | UUID | None = None,
    run_id: str | UUID | None = None,
    request_id: str | None = None,
    stage: str | None = None,
) -> Iterator[None]:
    """Bind the given context ids for the duration of the block; unbind on exit. Only the ids
    passed are bound, so nested contexts don't clobber ids they don't mention."""
    provided = {"user_id": user_id, "run_id": run_id, "request_id": request_id, "stage": stage}
    tokens = [
        (_CONTEXT_VARS[name], _CONTEXT_VARS[name].set(str(value)))
        for name, value in provided.items()
        if value is not None
    ]
    try:
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)


_http_logger = get_logger("http")


def _header(scope: Scope, name: str) -> str | None:
    target = name.lower().encode("latin-1")
    headers: list[tuple[bytes, bytes]] = scope.get("headers", [])
    for key, value in headers:
        if key.lower() == target:
            return value.decode("latin-1")
    return None


def _subject_from_scope(scope: Scope) -> str | None:
    """Best-effort JWT subject for the request log line. Never raises — an absent/invalid token
    just logs a null user (the real auth dependency still owns rejecting the request)."""
    auth = _header(scope, "authorization")
    if not auth:
        return None
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    try:
        return decode_service_jwt(token).sub
    except Exception:
        return None


class RequestContextMiddleware:
    """Pure-ASGI middleware: binds a request id (honoring an inbound `X-Request-ID`) and the JWT
    subject, echoes the id in the response header, and emits one structured line per request.

    Pure ASGI (not BaseHTTPMiddleware) so the context vars it sets are visible to the endpoint
    and pipeline that run inside the request, and reset deterministically afterward.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _header(scope, "x-request-id") or uuid.uuid4().hex
        rid_token = request_id_var.set(request_id)
        uid_token = user_id_var.set(_subject_from_scope(scope))
        status = {"code": 0}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                MutableHeaders(scope=message)["x-request-id"] = request_id
            await send(message)

        start = time.perf_counter()
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            _http_logger.info(
                "http.request",
                extra={
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                    "status": status["code"],
                    "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                },
            )
            user_id_var.reset(uid_token)
            request_id_var.reset(rid_token)


def _init_sentry(settings: Settings) -> None:
    if not settings.sentry_dsn:
        return
    try:
        import sentry_sdk  # type: ignore[import-not-found]
    except ImportError:
        get_logger("observability").warning("sentry_dsn set but sentry-sdk is not installed")
        return
    sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.app_env)


def _init_otel(settings: Settings) -> None:
    if not settings.otel_enabled:
        return
    # Init hook only — the OTLP exporter wiring is deferred with hosting (see the OBS brief).
    # Recording intent gives a later milestone a single place to attach a real tracer/exporter.
    get_logger("observability").info(
        "otel.enabled", extra={"note": "tracer/exporter wiring deferred"}
    )


def init_observability(settings: Settings) -> None:
    """Configure structured logging and, when their settings are on, the Sentry/OTel init hooks.
    Called once from `create_app`."""
    configure_logging(settings)
    _init_sentry(settings)
    _init_otel(settings)
