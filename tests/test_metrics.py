"""Pruebas unitarias de las métricas en memoria del proceso."""

from app.metrics import Metrics


def test_empty_metrics_have_the_exact_shape_with_zeros():
    snapshot = Metrics(slo_p95_ms=2000).snapshot(pid=123)
    assert snapshot == {
        "pid": 123,
        "requests": 0,
        "error_rate": 0.0,
        "latency_ms": {"p50": 0.0, "p95": 0.0},
        "tokens": {"input": 0, "output": 0},
        "slo": {"p95_ms_target": 2000, "met": True},
        "cost_usd": 0.0,
    }


def test_nearest_rank_percentiles_and_slo_not_met_when_p95_reaches_target():
    metrics = Metrics(slo_p95_ms=19)
    for latency in range(1, 21):
        metrics.record_request(200, float(latency))
    metrics.record_tokens(10, 2)
    metrics.record_tokens(5, 1)
    snapshot = metrics.snapshot(pid=1)
    assert snapshot["requests"] == 20
    assert snapshot["latency_ms"] == {"p50": 10.0, "p95": 19.0}
    assert snapshot["tokens"] == {"input": 15, "output": 3}
    assert snapshot["slo"] == {"p95_ms_target": 19, "met": False}


def test_error_rate_counts_only_server_errors():
    metrics = Metrics(slo_p95_ms=2000)
    for status in (200, 404, 422, 500):
        metrics.record_request(status, 1.0)
    assert metrics.snapshot(pid=1)["error_rate"] == 0.25


def test_latency_window_keeps_only_the_last_thousand_requests():
    metrics = Metrics(slo_p95_ms=2000)
    for _ in range(1000):
        metrics.record_request(200, 5000.0)
    for _ in range(1000):
        metrics.record_request(200, 10.0)
    assert metrics.snapshot(pid=1)["latency_ms"] == {"p50": 10.0, "p95": 10.0}
