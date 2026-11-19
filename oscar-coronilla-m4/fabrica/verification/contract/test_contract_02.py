"""Contrato de la sesión 2: cada petición se puede rastrear y medir."""

import uuid


def test_every_response_carries_a_request_id(api):
    request_id = api.get("/health").headers["X-Request-ID"]
    assert uuid.UUID(request_id)


def test_the_client_request_id_is_kept(api):
    response = api.post(
        "/ask", json={"question": "¿Quién es EMP-0004?"},
        headers={"X-Request-ID": "demo-123"},
    )
    assert response.headers["X-Request-ID"] == "demo-123"
    assert response.json()["request_id"] == "demo-123"


def test_metrics_report_latency_tokens_and_slo(api):
    api.post("/ask", json={"question": "¿Quién es EMP-0004?"})
    metrics = api.get("/metrics").json()
    assert metrics["requests"] >= 1
    assert set(metrics["latency_ms"]) == {"p50", "p95"}
    assert metrics["tokens"]["input"] > 0
    assert isinstance(metrics["slo"]["met"], bool)


def test_home_page_shows_the_request_id(api):
    assert "request_id" in api.get("/").text
