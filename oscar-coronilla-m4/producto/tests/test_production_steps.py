"""Pasos de los escenarios de ``features/production.feature``.

Contrato de la sesión 4: ``POST /ask`` y ``GET /metrics`` piden ``X-API-Key``;
el límite por cliente sale de ``rate_limit_per_minute`` y del reloj inyectado;
con ``environment="production"``, ``create_app()`` lanza ``ValueError`` (o una
subclase) si la configuración no cumple las reglas de compliance.
"""

import io
import json

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from app.main import create_app
from app.security import parse_api_keys

scenarios("features/production.feature")

QUESTION = "¿Quién es EMP-0004?"
WRONG_KEY = "wrong-key-that-must-not-leak"
OTHER_CLIENT = "other"
OTHER_KEY = "example-other-key-0002"
SMALL_MODEL = "@cf/meta/llama-3.1-8b-instruct-fast"
LARGE_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
SHORT_KEY = "web:" + "s" * 15
UNSAFE_CHANGES = {
    "uses the fake model": {"model_provider": "fake"},
    "has no API keys": {"api_keys": ()},
    "has a key of 15 characters": {"api_keys": parse_api_keys(SHORT_KEY)},
    "sends traces without hiding the texts": {
        "langsmith_tracing": True,
        "langsmith_key_present": True,
        "hide_inputs": False,
    },
}


@pytest.fixture
def context():
    """Guarda las respuestas, la clave enviada y la configuración de cada escenario."""
    return {"responses": [], "sent_key": None, "overrides": {}}


def _last(context):
    return context["responses"][-1]


@given("the assistant is running with a captured log", target_fixture="observed")
def assistant_with_captured_log(make_observed_app):
    return make_observed_app()


@given(
    parsers.parse(
        "the assistant is running with a limit of {limit:d} requests per minute"
    ),
    target_fixture="observed",
)
def assistant_with_rate_limit(
    make_observed_app, make_cost_settings, example_api_key, context, limit
):
    keys = f"tests:{example_api_key},{OTHER_CLIENT}:{OTHER_KEY}"
    context["keys"] = {"tests": example_api_key, OTHER_CLIENT: OTHER_KEY}
    settings = make_cost_settings(
        rate_limit_per_minute=limit, api_keys=parse_api_keys(keys)
    )
    return make_observed_app(settings=settings)


@when(parsers.parse('I call {method} "{path}" with {credential}'))
def call_with_credential(observed, context, method, path, credential):
    headers = {}
    if credential == "a wrong key":
        headers["X-API-Key"] = WRONG_KEY
        context["sent_key"] = WRONG_KEY
    response = observed.anonymous.request(
        method, path, json={"question": QUESTION}, headers=headers
    )
    context["responses"].append(response)


@when(parsers.parse('I ask "{question}" with the valid key'))
def ask_with_valid_key(observed, context, example_api_key, question):
    context["sent_key"] = example_api_key
    headers = {"X-API-Key": example_api_key}
    response = observed.anonymous.post(
        "/ask", json={"question": question}, headers=headers
    )
    context["responses"].append(response)


@when(parsers.parse('I open "{first}", "{second}" and "{third}" without a key'))
def open_public_paths(observed, context, first, second, third):
    for path in (first, second, third):
        context["responses"].append(observed.anonymous.get(path))


@when(parsers.re(r'the client "(?P<name>[^"]+)" asks (?P<count>\d+) questions?'))
def client_asks(observed, context, name, count):
    headers = {"X-API-Key": context["keys"][name]}
    for _ in range(int(count)):
        response = observed.anonymous.post(
            "/ask", json={"question": QUESTION}, headers=headers
        )
        context["responses"].append(response)


@when(parsers.parse("{seconds:d} seconds pass"))
def seconds_pass(observed, seconds):
    observed.clock.advance(seconds)


@then(parsers.parse("the response status is {status:d}"))
def response_status_is(context, status):
    assert _last(context).status_code == status


@then("every response status is 200")
def every_status_is_ok(context):
    assert [response.status_code for response in context["responses"]] == [200] * len(
        context["responses"]
    )


@then(parsers.parse('the detail is "{detail}"'))
def detail_is(context, detail):
    assert _last(context).json() == {"detail": detail}


@then(parsers.parse("the response asks to retry after {seconds:d} seconds"))
def retry_after_is(context, seconds):
    assert _last(context).headers["Retry-After"] == str(seconds)


@then("the log does not contain the key that was sent")
def log_has_no_key(observed, context, example_api_key):
    log = observed.log_text()
    assert example_api_key not in log
    assert WRONG_KEY not in log
    if context["sent_key"]:
        assert context["sent_key"] not in log


@then(
    parsers.parse(
        'the "{first}", "{second}" and "{third}" events name the client "{client}"'
    )
)
def events_name_the_client(observed, first, second, third, client):
    for name in (first, second, third):
        events = observed.events(name)
        assert events, f"no {name} event"
        assert all(event["client"] == client for event in events)


@then("the home page has the API key field")
def home_page_has_key_field(context):
    assert 'data-testid="api-key"' in context["responses"][0].text


@given("a safe production configuration")
def safe_production_configuration(context, make_cost_settings, production_values):
    context["make_settings"] = make_cost_settings
    context["overrides"] = dict(production_values)


@when(parsers.parse("the configuration {change}"))
def change_configuration(context, change):
    context["overrides"].update(UNSAFE_CHANGES[change])


def _start(context, directory, scripted_model):
    model = scripted_model([json.dumps({"answer": "Hola."})])
    return create_app(
        settings=context["make_settings"](**context["overrides"]),
        directory=directory,
        models={SMALL_MODEL: model, LARGE_MODEL: model},
        log_stream=io.StringIO(),
    )


@then("the assistant refuses to start")
def assistant_refuses_to_start(context, directory, scripted_model):
    with pytest.raises(ValueError):
        _start(context, directory, scripted_model)


@then("the assistant starts and answers the health check")
def assistant_starts(context, directory, scripted_model):
    client = TestClient(_start(context, directory, scripted_model))
    assert client.get("/health").status_code == 200
