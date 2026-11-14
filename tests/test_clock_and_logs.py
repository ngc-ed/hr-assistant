"""Pruebas unitarias del reloj y del log en JSON."""

import io
import json
from datetime import timedelta

from app.clock import SystemClock
from app.logs import JsonLogger


def test_system_clock_reports_utc_time():
    clock = SystemClock()
    assert clock.now().utcoffset() == timedelta(0)
    assert isinstance(clock.monotonic(), float)


def test_each_event_is_one_json_line_with_the_common_fields(fixed_clock):
    stream = io.StringIO()
    logger = JsonLogger("hr-assistant", fixed_clock, stream=stream)
    logger.log("audit", "req-1", tool="get_employee", args={"name": "Sofía"})
    logger.log("request", "req-2", status=200)
    text = stream.getvalue()
    lines = [json.loads(line) for line in text.splitlines()]
    assert len(lines) == 2
    assert lines[0] == {
        "ts": "2026-01-15T10:30:00.000+00:00",
        "service": "hr-assistant",
        "event": "audit",
        "request_id": "req-1",
        "tool": "get_employee",
        "args": {"name": "Sofía"},
    }
    assert lines[1]["request_id"] == "req-2"
    assert "Sofía" in text


def test_logger_without_stream_writes_to_the_current_stdout(fixed_clock, capsys):
    logger = JsonLogger("hr-assistant", fixed_clock)
    logger.log("request", "req-1", status=200)
    line = json.loads(capsys.readouterr().out)
    assert line["event"] == "request"
    assert line["status"] == 200
