"""Pasos de los escenarios de ``features/pii.feature``.

Contrato del reto: con ``pii_detection=True`` (por omisión), ``POST /ask``
revisa la pregunta y todo el historial antes de llamar al modelo; si hay PII
responde ``422 {"detail": "sensitive data detected: <tipos>", "request_id"}``.
La respuesta del modelo se enmascara y ``AskResponse`` agrega ``pii_masked``.
Cada detección escribe ``pii_detected`` sin el valor, y ``/metrics`` cuenta
``pii_blocked`` y ``pii_masked``.
"""

import io
import json

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from app.agent import STEP_LIMIT_ANSWER
from app.main import create_app

scenarios("features/pii.feature")

CLEAN_REPLY = json.dumps({"answer": "Hola."})
SMALL_MODEL = "@cf/meta/llama-3.1-8b-instruct-fast"
LARGE_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"


@pytest.fixture
def context():
    """Guarda las respuestas, el modelo grabador y la configuración del escenario."""
    return {"responses": [], "model": None, "overrides": {}}


def _last(context):
    return context["responses"][-1]


def _types(text):
    """Convierte ``"email, phone"`` en ``["email", "phone"]`` (vacío si no hay)."""
    return [item.strip() for item in text.split(",") if item.strip()]


@given("the assistant is running with a recording model", target_fixture="observed")
def assistant_with_recording_model(make_observed_app, scripted_model, context):
    context["model"] = scripted_model([CLEAN_REPLY])
    return make_observed_app(model=context["model"])


@given(
    parsers.parse(
        "the assistant is running with a recording model and a history window of "
        "{size:d}"
    ),
    target_fixture="observed",
)
def assistant_with_small_window(
    make_observed_app, make_cost_settings, scripted_model, context, size
):
    context["model"] = scripted_model([CLEAN_REPLY])
    settings = make_cost_settings(history_window=size)
    return make_observed_app(model=context["model"], settings=settings)


@given(
    "the assistant is running with a recording model and PII detection turned off",
    target_fixture="observed",
)
def assistant_without_detection(
    make_observed_app, make_cost_settings, scripted_model, context
):
    context["model"] = scripted_model([CLEAN_REPLY])
    settings = make_cost_settings(pii_detection=False)
    return make_observed_app(model=context["model"], settings=settings)


@given("the assistant is running with the simulated models", target_fixture="observed")
def assistant_with_simulated_models(make_observed_app, make_cost_settings):
    return make_observed_app(settings=make_cost_settings())


@given(
    parsers.parse('the assistant is running with a model that answers "{answer}"'),
    target_fixture="observed",
)
def assistant_with_answer(make_observed_app, scripted_model, context, answer):
    context["model"] = scripted_model([json.dumps({"answer": answer})])
    return make_observed_app(model=context["model"])


@given(
    "the assistant is running with a model that answers with an empty text",
    target_fixture="observed",
)
def assistant_with_empty_answer(make_observed_app, scripted_model, context):
    context["model"] = scripted_model([json.dumps({"answer": ""})])
    return make_observed_app(model=context["model"])


@when(parsers.re(r'I ask "(?P<question>[^"]+)"'))
def ask(observed, context, question):
    response = observed.client.post("/ask", json={"question": question})
    context["responses"].append(response)


@when(
    parsers.parse(
        'I ask "{question}" after {count:d} history messages, the first with '
        '"{value}"'
    )
)
def ask_with_history(observed, context, question, count, value):
    history = [
        {
            "role": "user" if index % 2 == 0 else "assistant",
            "content": f"Mensaje número {index + 1}.",
        }
        for index in range(count)
    ]
    history[0]["content"] = f"Mi correo es {value}"
    response = observed.client.post(
        "/ask", json={"question": question, "history": history}
    )
    context["responses"].append(response)


@then(parsers.parse("the response status is {status:d}"))
def response_status_is(context, status):
    assert _last(context).status_code == status


@then(parsers.parse('the detail is "{detail}"'))
def detail_is(context, detail):
    assert _last(context).json()["detail"] == detail


@then("the response has a request id")
def response_has_request_id(context):
    assert _last(context).json()["request_id"]


@then(parsers.parse('the response does not contain "{value}"'))
def response_does_not_contain(context, value):
    assert value not in _last(context).text


@then("the model was not called")
def model_not_called(context):
    assert context["model"].calls == []


@then("the model was called")
def model_called(context):
    assert len(context["model"].calls) >= 1


@then(parsers.parse('the answer contains "{text}"'))
def answer_contains(context, text):
    assert text in _last(context).json()["answer"]


@then("the answer is the step limit message")
def answer_is_step_limit(context):
    assert _last(context).json()["answer"] == STEP_LIMIT_ANSWER


@then(parsers.re(r'the masked types are "(?P<types>[^"]*)"'))
def masked_types_are(context, types):
    assert _last(context).json()["pii_masked"] == _types(types)


@then(
    parsers.parse(
        'the log has a "pii_detected" event from the "{where}" with types "{types}"'
    )
)
def log_has_pii_event(observed, context, where, types):
    events = observed.events("pii_detected")
    assert len(events) == 1
    event = events[0]
    assert event["where"] == where
    assert list(event["types"]) == _types(types)
    assert event["client"] == "tests"
    assert event["request_id"] == _last(context).json()["request_id"]


@then(parsers.parse('the log does not contain "{value}"'))
def log_does_not_contain(observed, value):
    assert value not in observed.log_text()


@then(
    parsers.parse(
        "the metrics show {blocked:d} blocked and {masked:d} masked answers"
    )
)
def metrics_show_pii_counts(observed, blocked, masked):
    body = observed.client.get("/metrics").json()
    assert body["pii_blocked"] == blocked
    assert body["pii_masked"] == masked


@given("a safe production configuration")
def safe_production_configuration(context, make_cost_settings, production_values):
    context["make_settings"] = make_cost_settings
    context["overrides"] = dict(production_values)


@when("PII detection is turned off")
def turn_detection_off(context):
    context["overrides"]["pii_detection"] = False


@then("the assistant refuses to start")
def assistant_refuses_to_start(context, directory, scripted_model):
    model = scripted_model([CLEAN_REPLY])
    with pytest.raises(ValueError, match="PII_DETECTION"):
        create_app(
            settings=context["make_settings"](**context["overrides"]),
            directory=directory,
            models={SMALL_MODEL: model, LARGE_MODEL: model},
            log_stream=io.StringIO(),
        )
