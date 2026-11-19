"""Pruebas de ``app.gateway``: el modelo real detras de Cloudflare AI Gateway.

El cliente ``httpx`` se inyecta con ``MockTransport``: nunca se usa la red.
"""

import json

import httpx
import pytest

from app.config import Settings
from app.gateway import GatewayLanguageModel
from app.llm import ModelUnavailableError

SMALL_MODEL = "@cf/meta/llama-3.1-8b-instruct-fast"
TOKEN = "token-super-secreto"
EXPECTED_URL = (
    "https://gateway.ai.cloudflare.com/v1/account-1/gateway-1"
    "/workers-ai/v1/chat/completions"
)
QUESTION = [{"role": "user", "content": "¿Quién es EMP-0004?"}]


def gateway_settings(**overrides):
    """Configuracion valida de ``gateway`` con valores ajustables."""
    values = {
        "model_provider": "gateway",
        "cf_account_id": "account-1",
        "cf_gateway_id": "gateway-1",
        "cf_api_token": TOKEN,
    }
    values.update(overrides)
    return Settings(**values)


def make_model(handler, **overrides):
    """Crea el modelo chico con un transporte simulado."""
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return GatewayLanguageModel(SMALL_MODEL, gateway_settings(**overrides), client)


def ok_response(headers=None):
    """Respuesta valida del gateway con una respuesta final y su uso de tokens."""
    body = {
        "choices": [{"message": {"content": '{"answer": "Jorge Díaz"}'}}],
        "usage": {"prompt_tokens": 42, "completion_tokens": 7},
    }
    return httpx.Response(200, json=body, headers=headers or {})


def test_request_has_the_exact_url_headers_and_body():
    sent = []

    def handler(request):
        sent.append(request)
        return ok_response()

    make_model(handler, model_max_tokens=123, model_temperature=0.0).complete(QUESTION)

    request = sent[0]
    body = json.loads(request.content)
    assert request.method == "POST"
    assert str(request.url) == EXPECTED_URL
    assert request.headers["Authorization"] == f"Bearer {TOKEN}"
    assert body["model"] == SMALL_MODEL
    assert body["max_tokens"] == 123
    assert body["temperature"] == 0
    assert body["messages"][0]["role"] == "system"
    assert body["messages"][-1] == QUESTION[0]


def test_cache_header_is_sent_only_when_the_ttl_is_positive():
    sent = []

    def handler(request):
        sent.append(request)
        return ok_response()

    make_model(handler, cache_ttl_seconds=0).complete(QUESTION)
    make_model(handler, cache_ttl_seconds=120).complete(QUESTION)

    assert "cf-aig-cache-ttl" not in sent[0].headers
    assert sent[1].headers["cf-aig-cache-ttl"] == "120"


def test_gateway_auth_header_is_sent_only_when_the_aig_token_has_a_value():
    sent = []

    def handler(request):
        sent.append(request)
        return ok_response()

    make_model(handler, cf_aig_token="").complete(QUESTION)
    make_model(handler, cf_aig_token="aig-secreto").complete(QUESTION)

    assert "cf-aig-authorization" not in sent[0].headers
    assert sent[1].headers["cf-aig-authorization"] == "Bearer aig-secreto"
    assert sent[1].headers["Authorization"] == f"Bearer {TOKEN}"


def test_usage_tokens_and_cache_hit_are_read_from_the_response():
    fresh = make_model(lambda request: ok_response()).complete(QUESTION)
    cached = make_model(
        lambda request: ok_response({"cf-aig-cache-status": "HIT"})
    ).complete(QUESTION)

    assert json.loads(fresh.text) == {"answer": "Jorge Díaz"}
    assert (fresh.input_tokens, fresh.output_tokens) == (42, 7)
    assert fresh.cached is False
    assert cached.cached is True


def _server_error(_request):
    return httpx.Response(500, text=f"upstream failed for {TOKEN}")


def _timeout(request):
    raise httpx.ReadTimeout("timed out", request=request)


@pytest.mark.parametrize("handler", [_server_error, _timeout], ids=["500", "timeout"])
def test_gateway_failure_is_model_unavailable_without_the_token(handler):
    with pytest.raises(ModelUnavailableError) as raised:
        make_model(handler).complete(QUESTION)

    assert TOKEN not in str(raised.value)
