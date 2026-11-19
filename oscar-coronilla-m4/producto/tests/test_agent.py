"""Pruebas de ``app.agent``: el bucle con tope, con un modelo guionizado."""

import json

import pytest

from app.agent import Agent

STEP_LIMIT_ANSWER = (
    "No pude completar la respuesta. Intenta con una pregunta más concreta."
)
TOOL_PREFIX = "Resultado de la herramienta: "
QUESTION = [{"role": "user", "content": "¿Quién es EMP-0004?"}]


def tool_call(name, **args):
    """Arma el JSON con el que el modelo pide una herramienta."""
    return json.dumps({"tool": name, "args": args})


def answer(text):
    """Arma el JSON con el que el modelo responde."""
    return json.dumps({"answer": text})


def test_tool_result_is_sent_back_and_tokens_are_summed(directory, scripted_model):
    model = scripted_model(
        [tool_call("get_employee", employee_id="EMP-0004"), answer("Es Jorge.")],
        input_tokens=10,
        output_tokens=4,
    )
    agent = Agent(model=model, directory=directory, max_steps=3)

    result = agent.run(QUESTION)

    assert result.answer == "Es Jorge."
    assert result.steps == 2
    assert result.tools_used == ["get_employee"]
    assert (result.input_tokens, result.output_tokens) == (20, 8)
    last_message = model.calls[1][-1]
    assert last_message["role"] == "user"
    assert last_message["content"].startswith(TOOL_PREFIX)
    assert "Jorge Díaz" in last_message["content"]


def test_step_cap_returns_the_exact_message(directory, scripted_model):
    model = scripted_model([tool_call("search_by_department", department="Ventas")])
    agent = Agent(model=model, directory=directory, max_steps=3)

    result = agent.run(QUESTION)

    assert result.answer == STEP_LIMIT_ANSWER
    assert result.steps == 3
    assert len(model.calls) == 3


@pytest.mark.parametrize(
    "bad_reply",
    ["this is not json", tool_call("delete_employee", employee_id="EMP-0004")],
    ids=["invalid json", "unknown tool"],
)
def test_bad_model_reply_is_reported_to_the_model(
    directory, scripted_model, bad_reply
):
    model = scripted_model([bad_reply, answer("Listo.")])
    agent = Agent(model=model, directory=directory, max_steps=3)

    result = agent.run(QUESTION)

    assert result.answer == "Listo."
    assert result.steps == 2
    assert model.calls[1][-1]["content"].startswith(TOOL_PREFIX)


def test_observer_receives_each_tool_call_with_its_args(directory, scripted_model):
    model = scripted_model(
        [
            tool_call("get_employee", employee_id="EMP-0004"),
            tool_call("search_by_department", department="Ventas"),
            answer("Listo."),
        ]
    )
    agent = Agent(model=model, directory=directory, max_steps=3)
    seen = []

    agent.run(QUESTION, observer=lambda tool, args: seen.append((tool, args)))

    assert seen == [
        ("get_employee", {"employee_id": "EMP-0004"}),
        ("search_by_department", {"department": "Ventas"}),
    ]


def test_stopped_is_true_only_when_the_step_cap_is_reached(
    directory, scripted_model
):
    answering = Agent(
        model=scripted_model([answer("Listo.")]), directory=directory, max_steps=1
    )
    looping = Agent(
        model=scripted_model([tool_call("get_employee", employee_id="EMP-0001")]),
        directory=directory,
        max_steps=1,
    )

    assert answering.run(QUESTION).stopped is False
    assert looping.run(QUESTION).stopped is True
