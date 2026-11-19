"""Pruebas de ``app.config``: valores por omision y valores invalidos."""

from pathlib import Path

import pytest

from app.config import Settings


def test_settings_use_documented_defaults():
    settings = Settings.from_env({})

    assert settings.model_provider == "fake"
    assert settings.agent_max_steps == 3
    assert settings.max_question_chars == 2000
    assert Path(settings.employees_path).parts[-2:] == ("data", "employees.json")


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("AGENT_MAX_STEPS", "0"),
        ("AGENT_MAX_STEPS", "-2"),
        ("AGENT_MAX_STEPS", "three"),
        ("MODEL_PROVIDER", "unknown"),
    ],
)
def test_invalid_setting_is_rejected_with_a_clear_message(variable, value):
    with pytest.raises(ValueError, match=variable):
        Settings.from_env({variable: value})


def test_observability_settings_use_safe_defaults():
    settings = Settings.from_env({})

    assert settings.service_name == "hr-assistant"
    assert settings.slo_p95_ms == 2000
    assert settings.langsmith_tracing is False
    assert settings.hide_inputs is True
    assert settings.hide_outputs is True
    assert settings.tracing_enabled is False


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("SLO_P95_MS", "fast"),
        ("SLO_P95_MS", "0"),
        ("LANGSMITH_TRACING", "maybe"),
        ("HIDE_INPUTS", "maybe"),
    ],
)
def test_invalid_observability_setting_is_rejected(variable, value):
    with pytest.raises(ValueError, match=variable):
        Settings.from_env({variable: value})


def test_tracing_needs_the_flag_and_the_key_and_never_keeps_the_key():
    only_flag = Settings.from_env({"LANGSMITH_TRACING": "TRUE"})
    flag_and_key = Settings.from_env(
        {
            "LANGSMITH_TRACING": "true",
            "LANGSMITH_API_KEY": "lsv2-secret-key",
            "HIDE_OUTPUTS": "False",
        }
    )

    assert only_flag.langsmith_tracing is True
    assert only_flag.tracing_enabled is False
    assert flag_and_key.tracing_enabled is True
    assert flag_and_key.hide_outputs is False
    assert "lsv2-secret-key" not in repr(flag_and_key)
