"""Contrato de la sesión 4: solo entra quien tiene clave, y nadie abusa."""

import os
import subprocess
import sys

import httpx

from verification.server import PRODUCT

QUESTION = {"question": "¿Quién es EMP-0004?"}


def test_asking_without_a_key_returns_401(api):
    response = httpx.post(f"{api.base_url}/ask", json=QUESTION)
    assert response.status_code == 401


def test_asking_with_a_wrong_key_returns_401(api):
    response = api.post("/ask", json=QUESTION, headers={"X-API-Key": "wrong"})
    assert response.status_code == 401


def test_health_and_page_need_no_key(api):
    assert httpx.get(f"{api.base_url}/health").status_code == 200
    assert 'data-testid="api-key"' in httpx.get(f"{api.base_url}/").text


def test_too_many_requests_returns_429_with_retry_after(api_limited):
    codes = [api_limited.post("/ask", json=QUESTION) for _ in range(3)]
    assert [c.status_code for c in codes] == [200, 200, 429]
    assert int(codes[-1].headers["Retry-After"]) > 0


def start(**env):
    settings = {**os.environ, "ENVIRONMENT": "development", **env}
    command = [sys.executable, "-c", "import app.main"]
    return subprocess.run(command, cwd=PRODUCT, env=settings, capture_output=True,
                          text=True, timeout=30, check=False)


def test_production_refuses_the_fake_model():
    started = start(
        ENVIRONMENT="production", MODEL_PROVIDER="fake", API_KEYS="a:" + "k" * 20
    )
    assert started.returncode != 0


def test_a_broken_api_keys_never_leaks_the_key():
    started = start(API_KEYS="secret-value-without-client")
    assert started.returncode != 0
    assert "secret-value-without-client" not in started.stderr
