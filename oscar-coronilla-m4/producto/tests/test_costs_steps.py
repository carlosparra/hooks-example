"""Pasos de los escenarios de ``features/costs.feature``.

Nunca se usa la red: el gateway se simula con ``httpx.MockTransport``.
"""

import httpx
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from app.gateway import GatewayLanguageModel

scenarios("features/costs.feature")

SMALL_MODEL = "@cf/meta/llama-3.1-8b-instruct-fast"
LARGE_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
GATEWAY_TOKEN = "token-super-secreto"
GATEWAY_SETTINGS = {
    "model_provider": "gateway",
    "cf_account_id": "account-1",
    "cf_gateway_id": "gateway-1",
    "cf_api_token": GATEWAY_TOKEN,
}


@pytest.fixture
def context():
    """Guarda las respuestas de cada escenario."""
    return {"responses": []}


def _last(context):
    return context["responses"][-1]


def _gateway_models(settings, handler):
    """Crea los dos modelos del gateway con un cliente HTTP simulado."""
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return {
        name: GatewayLanguageModel(name, settings, client)
        for name in (settings.model_small, settings.model_large)
    }


@given(
    "the assistant is running with the simulated models", target_fixture="observed"
)
def assistant_with_simulated_models(make_cost_app):
    return make_cost_app()


@given(
    "the assistant is running with routing turned off", target_fixture="observed"
)
def assistant_with_routing_off(make_cost_app, make_cost_settings):
    return make_cost_app(settings=make_cost_settings(routing=False))


@given(
    parsers.parse(
        "the assistant is running with a recording model and a history window of "
        "{window:d}"
    ),
    target_fixture="observed",
)
def assistant_with_recording_model(
    make_cost_app, make_cost_settings, scripted_model, context, window
):
    recorder = scripted_model(['{"answer": "Listo"}'])
    context["recorder"] = recorder
    return make_cost_app(
        settings=make_cost_settings(history_window=window),
        models={SMALL_MODEL: recorder, LARGE_MODEL: recorder},
    )


@given(
    "the assistant is running with a gateway that fails", target_fixture="observed"
)
def assistant_with_failing_gateway(make_cost_app, make_cost_settings):
    settings = make_cost_settings(**GATEWAY_SETTINGS)

    def handler(_request):
        return httpx.Response(500, json={"error": f"bad token {GATEWAY_TOKEN}"})

    return make_cost_app(settings=settings, models=_gateway_models(settings, handler))


@given(
    "the assistant is running with a gateway that answers from its cache",
    target_fixture="observed",
)
def assistant_with_cached_gateway(make_cost_app, make_cost_settings):
    settings = make_cost_settings(**GATEWAY_SETTINGS)

    def handler(_request):
        content = '{"answer": "Hola, soy el asistente"}'
        body = {
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 5},
        }
        return httpx.Response(200, json=body, headers={"cf-aig-cache-status": "HIT"})

    return make_cost_app(settings=settings, models=_gateway_models(settings, handler))


@when(parsers.re(r'I ask "(?P<question>[^"]+)"$'))
def ask(observed, context, question):
    context["responses"].append(
        observed.client.post("/ask", json={"question": question})
    )


@when(parsers.parse('I ask "{question}" with the request id "{request_id}"'))
def ask_with_id(observed, context, question, request_id):
    response = observed.client.post(
        "/ask", json={"question": question}, headers={"X-Request-ID": request_id}
    )
    context["responses"].append(response)


@when(parsers.parse('I ask a question of {length:d} characters about "{employee}"'))
def ask_long_question(observed, context, length, employee):
    question = (f"¿Quién es {employee}? " + "a" * length)[:length]
    assert len(question) == length
    context["responses"].append(
        observed.client.post("/ask", json={"question": question})
    )


@when(parsers.parse('I ask "{question}" after {count:d} history messages'))
def ask_with_history(observed, context, question, count):
    history = [
        {"role": "user" if index % 2 == 0 else "assistant", "content": f"m{index}"}
        for index in range(count)
    ]
    context["responses"].append(
        observed.client.post("/ask", json={"question": question, "history": history})
    )


@when("I read the metrics")
def read_metrics(observed, context):
    context["responses"].append(observed.client.get("/metrics"))


@then(parsers.parse("the response status is {status:d}"))
def response_status_is(context, status):
    assert _last(context).status_code == status


@then("the answer used the small model")
def used_small_model(context):
    assert _last(context).json()["model"] == SMALL_MODEL


@then("the answer used the large model")
def used_large_model(context):
    assert _last(context).json()["model"] == LARGE_MODEL


@then(parsers.parse('the route is "{reason}"'))
def route_is(context, reason):
    assert _last(context).json()["route"] == reason


@then("the cost is greater than zero")
def cost_is_positive(context):
    assert _last(context).json()["cost_usd"] > 0


@then("the cost is zero")
def cost_is_zero(context):
    assert _last(context).json()["cost_usd"] == 0


@then(parsers.parse("the model received {count:d} messages"))
def model_received_messages(context, count):
    assert len(context["recorder"].calls[0]) == count


@then(parsers.parse('the last message the model received is "{content}"'))
def last_message_is(context, content):
    assert context["recorder"].calls[0][-1] == {"role": "user", "content": content}


@then(
    parsers.parse('the body is model unavailable with the request id "{request_id}"')
)
def body_is_model_unavailable(context, request_id):
    assert _last(context).json() == {
        "detail": "model unavailable",
        "request_id": request_id,
    }


@then(parsers.parse('the log has {count:d} "{name}" event'))
def log_has_events(observed, count, name):
    assert len(observed.events(name)) == count


@then("the log does not contain the gateway token")
def log_has_no_token(observed):
    assert GATEWAY_TOKEN not in observed.log_text()


@then("every call was cached")
def every_call_was_cached(context):
    body = _last(context).json()
    assert body["steps"] >= 1
    assert body["cached_calls"] == body["steps"]


@then("the metrics cost is the sum of both answers")
def metrics_cost_is_sum(context):
    first, second, metrics = context["responses"]
    expected = first.json()["cost_usd"] + second.json()["cost_usd"]
    assert expected > 0
    assert metrics.json()["cost_usd"] == pytest.approx(expected)
