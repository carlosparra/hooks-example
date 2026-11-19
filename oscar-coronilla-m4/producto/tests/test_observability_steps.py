"""Pasos de los escenarios de ``features/observability.feature``."""

import uuid

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features/observability.feature")


@pytest.fixture
def context():
    """Guarda la aplicacion observada y las respuestas de cada escenario."""
    return {"responses": [], "questions": []}


def _last(context):
    return context["responses"][-1]


@given("the assistant is running with a captured log", target_fixture="observed")
def assistant_with_captured_log(make_observed_app):
    return make_observed_app()


@given("the assistant is running with a broken model", target_fixture="observed")
def assistant_with_broken_model(make_observed_app, broken_model):
    return make_observed_app(model=broken_model)


@when("I check the health")
def check_health(observed, context):
    context["responses"].append(observed.client.get("/health"))


@when(parsers.parse('I check the health with the request id "{request_id}"'))
def check_health_with_id(observed, context, request_id):
    response = observed.client.get("/health", headers={"X-Request-ID": request_id})
    context["responses"].append(response)


@when(parsers.parse('I send "{question}" with the request id "{request_id}"'))
def send_with_id(observed, context, question, request_id):
    response = observed.client.post(
        "/ask", json={"question": question}, headers={"X-Request-ID": request_id}
    )
    context["questions"].append(question)
    context["responses"].append(response)


@when("I read the metrics")
def read_metrics(observed, context):
    context["responses"].append(observed.client.get("/metrics"))


@then("the response request id is a UUID")
def request_id_is_uuid(context):
    assert uuid.UUID(_last(context).headers["X-Request-ID"])


@then(parsers.parse('the response request id is "{request_id}"'))
def header_request_id_is(context, request_id):
    assert _last(context).headers["X-Request-ID"] == request_id


@then(parsers.parse('the body request id is "{request_id}"'))
def body_request_id_is(context, request_id):
    assert _last(context).json()["request_id"] == request_id


@then(parsers.parse("the response status is {status:d}"))
def response_status_is(context, status):
    assert _last(context).status_code == status


@then(
    parsers.parse('the body is the internal error with the request id "{request_id}"')
)
def body_is_internal_error(context, request_id):
    assert _last(context).json() == {
        "detail": "internal error",
        "request_id": request_id,
    }
    assert _last(context).headers["X-Request-ID"] == request_id


@then(parsers.parse('the log has {count:d} "{name}" event'))
def log_has_events(observed, count, name):
    assert len(observed.events(name)) == count


@then(parsers.parse('the audit event names the tool "{tool}"'))
def audit_names_tool(observed, tool):
    audit = observed.events("audit")[0]
    assert audit["action"] == "tool_call"
    assert audit["tool"] == tool
    assert audit["args"] == {"employee_id": "EMP-0004"}


@then(
    parsers.parse(
        'every event has the service "{service}" and the request id "{request_id}"'
    )
)
def every_event_has_common_fields(observed, service, request_id):
    events = observed.events()
    assert events
    for event in events:
        assert event["service"] == service
        assert event["request_id"] == request_id
        assert event["ts"]


@then("the log does not contain the question or the answer")
def log_has_no_personal_text(observed, context):
    log = observed.log_text()
    assert context["questions"][-1] not in log
    assert _last(context).json()["answer"] not in log
    assert "Jorge Díaz" not in log


@then(parsers.parse('the error event has the type "{error_type}"'))
def error_event_has_type(observed, error_type):
    assert observed.events("error")[0]["error_type"] == error_type


@then("the log does not contain the error message")
def log_has_no_error_message(observed, broken_model):
    assert broken_model.MESSAGE not in observed.log_text()
    assert "clave-xyz" not in observed.log_text()


@then("the metrics count at least 1 request")
def metrics_count_requests(context):
    assert _last(context).json()["requests"] >= 1


@then("the metrics report input tokens")
def metrics_report_tokens(context):
    assert _last(context).json()["tokens"]["input"] > 0


@then("the SLO result is a boolean")
def slo_result_is_boolean(context):
    assert isinstance(_last(context).json()["slo"]["met"], bool)
