"""Pruebas de la prueba de humo, con un servidor simulado (sin red)."""

import httpx

from verification import production


def fake_render(key_required=True, healthy=True):
    def handler(request):
        if request.url.path == "/health":
            return httpx.Response(200 if healthy else 503)
        has_key = request.headers.get("X-API-Key") == "good-key"
        return httpx.Response(200 if has_key or not key_required else 401)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_a_healthy_protected_service_passes(capsys):
    assert production.smoke("https://x", "good-key", fake_render())
    assert capsys.readouterr().out.count("[OK]") == 3


def test_a_service_without_keys_fails():
    open_service = fake_render(key_required=False)
    assert not production.smoke("https://x", "good-key", open_service)


def test_a_sleeping_service_fails():
    assert not production.smoke("https://x", "good-key", fake_render(healthy=False))


def test_the_key_must_come_from_the_environment(monkeypatch, capsys):
    monkeypatch.delenv("SMOKE_API_KEY", raising=False)
    assert production.main(["https://x"]) == 2
    assert "SMOKE_API_KEY" in capsys.readouterr().out
