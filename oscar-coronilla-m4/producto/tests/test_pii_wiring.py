"""Pruebas de lo que une la PII con el resto del producto.

Compliance (``RULE_PII_ON``), metadatos de la traza (``pii_types``) y el
mensaje de la página para un ``422`` por datos sensibles.
"""

from app.compliance import RULE_PII_ON, violations
from app.config import Settings
from app.tracing import NoopTracer, build_tracer

SENSITIVE_MESSAGE = (
    "Tu pregunta contiene datos sensibles; elimínalos y vuelve a intentar"
)


class FakeTraceable:
    """Imita ``langsmith.traceable``: anota sus opciones y no cambia la función."""

    def __init__(self):
        self.options = []

    def __call__(self, **options):
        self.options.append(options)
        return lambda func: func


def check_input(types):
    """Función de ejemplo que se envuelve en la prueba de trazas."""
    return types


def test_production_requires_pii_detection_but_development_does_not(
    make_cost_settings, production_values
):
    production = make_cost_settings(**production_values, pii_detection=False)
    development = make_cost_settings(pii_detection=False)

    assert violations(production) == [RULE_PII_ON]
    assert "PII_DETECTION" in RULE_PII_ON
    assert not violations(development)


def test_trace_metadata_carries_the_pii_types_only():
    settings = Settings.from_env(
        {"LANGSMITH_TRACING": "true", "LANGSMITH_API_KEY": "test-key"}
    )
    traceable = FakeTraceable()
    tracer = build_tracer(settings, traceable=traceable)

    tracer.wrap(
        check_input,
        name="pii_input",
        run_type="chain",
        request_id="req-9",
        pii_types=("email",),
    )

    assert list(traceable.options[0]["metadata"]["pii_types"]) == ["email"]
    noop = NoopTracer().wrap(
        check_input, name="pii_input", run_type="chain", request_id="r", pii_types=()
    )
    assert noop is check_input


def test_page_shows_the_sensitive_data_message(make_observed_app):
    page = make_observed_app().anonymous.get("/")

    assert page.status_code == 200
    assert SENSITIVE_MESSAGE in page.text
