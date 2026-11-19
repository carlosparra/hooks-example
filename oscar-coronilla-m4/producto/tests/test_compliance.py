"""Pruebas de ``app.compliance``: reglas de producción revisadas al arrancar.

Contrato: ``violations(settings)`` devuelve una lista con una entrada por regla
violada; ``enforce(settings)`` lanza ``ComplianceError`` (subclase de
``ValueError``) si la lista no está vacía.
"""

import pytest

from app.compliance import ComplianceError, enforce, violations
from app.security import parse_api_keys

SHORT_KEY = "short-key-15chr"


def test_development_requires_nothing(make_cost_settings):
    settings = make_cost_settings(environment="development", api_keys=())

    found = violations(settings)
    assert isinstance(found, list)
    assert not found
    enforce(settings)


def test_production_reports_every_broken_rule_without_the_keys(make_cost_settings):
    settings = make_cost_settings(
        environment="production",
        model_provider="fake",
        api_keys=parse_api_keys(f"web:{SHORT_KEY}"),
        langsmith_tracing=True,
        langsmith_key_present=True,
        hide_outputs=False,
    )

    assert len(violations(settings)) == 3
    with pytest.raises(ComplianceError) as error:
        enforce(settings)
    assert isinstance(error.value, ValueError)
    assert SHORT_KEY not in str(error.value)
