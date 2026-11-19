"""Pruebas de ``app.llm``: reglas del modelo simulado y conteo de tokens."""

import json

import pytest

from app.llm import FakeLanguageModel

DEPARTMENTS = ["Tecnología", "Ventas", "Finanzas"]


@pytest.fixture
def model():
    """Modelo simulado que conoce los departamentos de los datos de prueba."""
    return FakeLanguageModel(DEPARTMENTS)


def ask(model, content):
    """Manda un solo mensaje de usuario y devuelve el JSON de la respuesta."""
    reply = model.complete([{"role": "user", "content": content}])
    return json.loads(reply.text)


def test_tool_result_becomes_the_answer(model):
    reply = ask(model, "Resultado de la herramienta: Jorge Díaz, Líder técnico")

    assert reply == {"answer": "Según el directorio: Jorge Díaz, Líder técnico"}


def test_employee_id_requests_get_employee_even_if_a_department_is_named(model):
    reply = ask(model, "¿EMP-0004 trabaja en Finanzas?")

    assert reply == {"tool": "get_employee", "args": {"employee_id": "EMP-0004"}}


def test_department_without_accent_requests_search_by_department(model):
    reply = ask(model, "¿Quiénes están en tecnologia?")

    assert reply == {
        "tool": "search_by_department",
        "args": {"department": "Tecnología"},
    }


def test_tokens_are_counted_as_words(model):
    messages = [
        {"role": "user", "content": "Hola"},
        {"role": "assistant", "content": "Hola, ¿en qué te ayudo?"},
        {"role": "user", "content": "Nada más"},
    ]

    reply = model.complete(messages)

    assert reply.input_tokens == 8
    assert reply.output_tokens == len(reply.text.split())
