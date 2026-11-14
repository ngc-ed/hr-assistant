"""Pruebas de la línea ``request`` del log con el reloj inyectado."""

import io
import json


def test_request_latency_and_timestamp_come_from_the_injected_clock(
    make_client, fixed_clock
):
    stream = io.StringIO()
    client = make_client(clock=fixed_clock, log_stream=stream)
    response = client.get("/health", headers={"X-Request-ID": "lat-1"})
    lines = [json.loads(line) for line in stream.getvalue().splitlines()]
    (request_line,) = [line for line in lines if line["event"] == "request"]
    assert response.headers["X-Request-ID"] == "lat-1"
    assert request_line == {
        "ts": "2026-01-15T10:30:00.000+00:00",
        "service": "hr-assistant",
        "event": "request",
        "request_id": "lat-1",
        "method": "GET",
        "path": "/health",
        "status": 200,
        "latency_ms": 250.0,
    }
