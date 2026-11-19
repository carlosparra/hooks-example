"""Pruebas de la configuración del reto: ``PII_DETECTION`` y ``OUTPUT_MAX_CHARS``."""

import pytest

from app.config import Settings


def test_pii_detection_is_on_and_answers_are_capped_by_default():
    settings = Settings.from_env({})

    assert settings.pii_detection is True
    assert settings.output_max_chars == 2000


def test_invalid_pii_settings_are_rejected():
    with pytest.raises(ValueError, match="PII_DETECTION"):
        Settings.from_env({"PII_DETECTION": "si"})
    for raw in ("0", "abc"):
        with pytest.raises(ValueError, match="OUTPUT_MAX_CHARS"):
            Settings.from_env({"OUTPUT_MAX_CHARS": raw})
