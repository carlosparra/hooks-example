"""Pasos de los escenarios de ``features/assistant.feature``."""

import json
import os

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from app.main import create_app

scenarios("features/assistant.feature")

INVALID_QUESTIONS = {
    "empty": "",
    "blank": "   ",
    "too long": "a" * 2001,
}


@pytest.fixture
def context():
    """Guarda las respuestas HTTP de cada escenario."""
    return {"responses": []}


def _client(settings, directory, headers, model=None):
    application = create_app(settings=settings, model=model, directory=directory)
    return TestClient(application, headers=headers)


@given("the assistant is running", target_fixture="client")
def assistant_running(make_settings, directory, auth_headers):
    return _client(make_settings(), directory, auth_headers)


@given(
    parsers.parse("the assistant is running with at most {steps:d} step"),
    target_fixture="client",
)
def assistant_with_step_cap(make_settings, directory, auth_headers, steps):
    return _client(make_settings(agent_max_steps=steps), directory, auth_headers)


@given("the assistant is running with a recording model", target_fixture="client")
def assistant_with_recording_model(
    make_settings, directory, auth_headers, scripted_model, context
):
    model = scripted_model([json.dumps({"answer": "Listo."})])
    context["model"] = model
    return _client(make_settings(), directory, auth_headers, model=model)


@when(parsers.parse('I send the history "{previous}" and ask "{question}"'))
def ask_with_history(client, context, question, previous):
    history = [{"role": "user", "content": previous}]
    response = client.post("/ask", json={"question": question, "history": history})
    context["responses"].append(response)


@when(parsers.parse('I ask "{question}"'))
def ask(client, context, question):
    context["responses"].append(client.post("/ask", json={"question": question}))


@when(parsers.parse("I send a {kind} question"))
def send_invalid_question(client, context, kind):
    question = INVALID_QUESTIONS[kind]
    context["responses"].append(client.post("/ask", json={"question": question}))


@when("I check the health")
def check_health(client, context):
    context["responses"].append(client.get("/health"))


@when("I open the home page")
def open_home_page(client, context):
    context["responses"].append(client.get("/"))


@then("the request succeeds")
def request_succeeds(context):
    assert context["responses"][-1].status_code == 200


@then("the request is rejected as invalid")
def request_rejected(context):
    assert context["responses"][-1].status_code == 422


@then(parsers.parse('the answer contains "{text}"'))
def answer_contains(context, text):
    assert text in context["responses"][-1].json()["answer"]


@then(parsers.parse('the answer is "{text}"'))
def answer_is(context, text):
    assert context["responses"][-1].json()["answer"] == text


@then(parsers.parse('the tools used are "{tool}"'))
def tools_used_are(context, tool):
    assert context["responses"][-1].json()["tools_used"] == [tool]


@then("no tools were used")
def no_tools_used(context):
    assert context["responses"][-1].json()["tools_used"] == []


@then(parsers.parse("the agent took {steps:d} steps"))
def agent_took_steps(context, steps):
    assert context["responses"][-1].json()["steps"] == steps


@then("the first model call received the history and the question")
def first_call_has_history(context):
    first_call = context["model"].calls[0]
    assert [message["content"] for message in first_call] == [
        "Hola",
        "¿Quién es EMP-0004?",
    ]


@then("the second model call received only the question")
def second_call_has_only_question(context):
    second_call = context["model"].calls[1]
    assert second_call == [{"role": "user", "content": "¿Quién es EMP-0004?"}]


@then(parsers.parse('the health status is "{status}" with the process id'))
def health_status(context, status):
    body = context["responses"][-1].json()
    assert body == {"status": status, "pid": os.getpid()}


@then(parsers.parse('the page has the elements "{first}", "{second}" and "{third}"'))
def page_has_elements(context, first, second, third):
    page = context["responses"][-1].text
    for test_id in (first, second, third):
        assert f'data-testid="{test_id}"' in page
