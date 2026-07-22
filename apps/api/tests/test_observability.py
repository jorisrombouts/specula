"""Structured logging + request-id middleware (OBS lane). No DB — /health is unauthenticated,
and the middleware decodes the bearer token's subject itself for the request log line."""

import json
import logging
import uuid
from collections.abc import Iterator

import pytest
from httpx import ASGITransport, AsyncClient

from specula_api.auth import mint
from specula_api.config import Settings, settings
from specula_api.main import create_app
from specula_api.observability import (
    ContextFilter,
    JsonFormatter,
    configure_logging,
    get_logger,
    log_context,
    request_id_var,
    run_id_var,
    stage_var,
    user_id_var,
)


class _CaptureHandler(logging.Handler):
    """Formats each record through the real JsonFormatter (with the context filter) and keeps
    the resulting JSON line, so a test can assert on what would be written to stdout."""

    def __init__(self) -> None:
        super().__init__()
        self.addFilter(ContextFilter())
        self.setFormatter(JsonFormatter())
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))


@pytest.fixture
def capture() -> Iterator[_CaptureHandler]:
    handler = _CaptureHandler()
    logger = logging.getLogger("specula")
    logger.addHandler(handler)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)


@pytest.fixture(autouse=True)
def _service_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "service_jwt_secret", "test-secret-at-least-32-bytes-long")


def test_json_formatter_includes_context_fields() -> None:
    tokens = [
        request_id_var.set("req-123"),
        user_id_var.set("user-abc"),
        run_id_var.set("run-9"),
        stage_var.set("extract"),
    ]
    try:
        record = logging.LogRecord("specula.test", logging.INFO, __file__, 1, "hi", None, None)
        ContextFilter().filter(record)
        obj = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(tokens[0])
        user_id_var.reset(tokens[1])
        run_id_var.reset(tokens[2])
        stage_var.reset(tokens[3])

    assert obj["message"] == "hi"
    assert obj["level"] == "INFO"
    assert obj["logger"] == "specula.test"
    assert obj["request_id"] == "req-123"
    assert obj["user_id"] == "user-abc"
    assert obj["run_id"] == "run-9"
    assert obj["stage"] == "extract"
    assert "timestamp" in obj


def test_json_formatter_carries_extra_fields() -> None:
    record = logging.LogRecord(
        "specula.http", logging.INFO, __file__, 1, "http.request", None, None
    )
    record.__dict__["status"] = 200
    ContextFilter().filter(record)
    obj = json.loads(JsonFormatter().format(record))
    assert obj["status"] == 200
    # unset context fields serialize as null, not missing
    assert obj["request_id"] is None


def test_log_context_binds_then_resets() -> None:
    assert user_id_var.get() is None
    with log_context(user_id="u1", run_id="r1"):
        assert user_id_var.get() == "u1"
        assert run_id_var.get() == "r1"
    assert user_id_var.get() is None
    assert run_id_var.get() is None


def test_configure_logging_is_idempotent() -> None:
    configure_logging(Settings())
    logger = logging.getLogger("specula")
    count = len(logger.handlers)
    configure_logging(Settings())
    assert len(logger.handlers) == count


async def test_request_emits_json_line_with_request_and_user_id(capture: _CaptureHandler) -> None:
    sub = f"test-sub-{uuid.uuid4()}"
    token = mint(sub=sub, email="a@b.io", name="Test")
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    events = [json.loads(line) for line in capture.lines]
    http_events = [e for e in events if e["message"] == "http.request"]
    assert http_events, f"no http.request log captured; got {[e['message'] for e in events]}"
    event = http_events[-1]
    assert event["request_id"]
    assert event["user_id"] == sub
    assert event["path"] == "/health"
    assert event["status"] == 200


async def test_response_carries_request_id_header() -> None:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.headers.get("x-request-id")


async def test_stage_logger_line_carries_stage(capture: _CaptureHandler) -> None:
    with log_context(user_id="u1", run_id="r1"):
        get_logger("pipeline.extract").info("pipeline.stage", extra={"stage": "extract"})
    events = [json.loads(line) for line in capture.lines]
    stage_events = [e for e in events if e["message"] == "pipeline.stage"]
    assert stage_events
    assert stage_events[-1]["stage"] == "extract"
    assert stage_events[-1]["user_id"] == "u1"
    assert stage_events[-1]["run_id"] == "r1"
