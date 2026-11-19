"""Pruebas de ``app.tracing`` con un ``traceable`` falso: nunca se usa la red.

Contrato: ``build_tracer(settings, traceable=...)`` devuelve un ``NoopTracer``
si las trazas no estan encendidas; si lo estan, un tracer que llama
``traceable(run_type=..., name=..., metadata=..., process_inputs=...,
process_outputs=...)`` y aplica el decorador que este devuelve.
``tracer.wrap(func, name=..., run_type=..., request_id=...)`` envuelve una funcion.
"""

import json

from app.config import Settings
from app.tracing import NoopTracer, build_tracer

QUESTION = "¿Quién es EMP-0004?"


class FakeTraceable:
    """Imita ``langsmith.traceable``: anota sus opciones y no cambia la funcion."""

    def __init__(self):
        self.options = []

    def __call__(self, **options):
        self.options.append(options)
        return lambda func: func


def lookup(question):
    """Funcion de ejemplo que se envuelve en las pruebas."""
    return f"respuesta a {question}"


def test_noop_tracer_returns_the_same_function():
    tracer = NoopTracer()

    wrapped = tracer.wrap(lookup, name="lookup", run_type="tool", request_id="r-1")

    assert wrapped is lookup


def test_tracing_without_api_key_uses_the_noop_tracer():
    settings = Settings.from_env({"LANGSMITH_TRACING": "true"})
    traceable = FakeTraceable()

    tracer = build_tracer(settings, traceable=traceable)

    assert isinstance(tracer, NoopTracer)
    assert tracer.wrap(lookup, name="x", run_type="tool", request_id="r") is lookup
    assert not traceable.options


def test_enabled_tracer_tags_the_request_id_and_hides_the_texts():
    settings = Settings.from_env(
        {"LANGSMITH_TRACING": "true", "LANGSMITH_API_KEY": "test-key"}
    )
    traceable = FakeTraceable()
    tracer = build_tracer(settings, traceable=traceable)

    wrapped = tracer.wrap(lookup, name="lookup", run_type="chain", request_id="req-7")

    assert wrapped(QUESTION) == f"respuesta a {QUESTION}"
    options = traceable.options[0]
    assert options["name"] == "lookup"
    assert options["run_type"] == "chain"
    assert options["metadata"]["request_id"] == "req-7"
    hidden_inputs = options["process_inputs"]({"question": QUESTION})
    hidden_outputs = options["process_outputs"]({"output": "Jorge Díaz"})
    assert "EMP-0004" not in json.dumps(hidden_inputs, ensure_ascii=False)
    assert "Jorge Díaz" not in json.dumps(hidden_outputs, ensure_ascii=False)
