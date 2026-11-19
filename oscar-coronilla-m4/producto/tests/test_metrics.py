"""Pruebas de ``app.metrics``: percentiles, tasa de error, ventana y SLO.

Los percentiles usan el metodo de rango mas cercano. Solo las respuestas
``5xx`` cuentan como error del servidor.
"""

import os

from app.metrics import Metrics


def test_percentiles_use_the_nearest_rank():
    metrics = Metrics()
    for latency in (10, 20, 30, 40, 50, 60, 70, 80, 90, 100):
        metrics.record_request(latency_ms=latency, status=200)

    snapshot = metrics.snapshot(slo_p95_ms=2000)

    assert snapshot["latency_ms"] == {"p50": 50, "p95": 100}
    assert snapshot["requests"] == 10
    assert snapshot["pid"] == os.getpid()


def test_empty_metrics_report_zeros():
    snapshot = Metrics().snapshot(slo_p95_ms=2000)

    assert snapshot == {
        "pid": os.getpid(),
        "requests": 0,
        "error_rate": 0,
        "latency_ms": {"p50": 0, "p95": 0},
        "tokens": {"input": 0, "output": 0},
        "slo": {"p95_ms_target": 2000, "met": True},
    }


def test_error_rate_counts_only_server_errors_and_tokens_are_summed():
    metrics = Metrics()
    for status in (200, 200, 422, 500):
        metrics.record_request(latency_ms=5, status=status)
    metrics.add_tokens(input_tokens=30, output_tokens=7)
    metrics.add_tokens(input_tokens=12, output_tokens=3)

    snapshot = metrics.snapshot(slo_p95_ms=2000)

    assert snapshot["error_rate"] == 0.25
    assert snapshot["tokens"] == {"input": 42, "output": 10}


def test_latency_window_keeps_only_the_most_recent_values():
    metrics = Metrics(window=3)
    for latency in (5000, 5000, 5000, 10, 10, 10):
        metrics.record_request(latency_ms=latency, status=200)

    snapshot = metrics.snapshot(slo_p95_ms=2000)

    assert snapshot["latency_ms"]["p95"] == 10
    assert snapshot["requests"] == 6


def test_slo_is_not_met_when_p95_equals_the_target():
    metrics = Metrics()
    metrics.record_request(latency_ms=2000, status=200)

    assert metrics.snapshot(slo_p95_ms=2000)["slo"] == {
        "p95_ms_target": 2000,
        "met": False,
    }
    assert metrics.snapshot(slo_p95_ms=2001)["slo"]["met"] is True
