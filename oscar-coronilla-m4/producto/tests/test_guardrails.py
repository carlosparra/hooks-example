"""Pruebas de ``app.guardrails``: validación de la respuesta del modelo.

Contrato: ``validate_output(text, max_chars, pii_enabled)`` devuelve un objeto
con ``text`` y ``masked_types``. Una respuesta vacía se cambia por el mensaje
de tope de pasos; después se enmascara la PII y al final se recorta.
"""

from app.agent import STEP_LIMIT_ANSWER
from app.guardrails import validate_output


def test_empty_or_blank_answer_becomes_the_step_limit_message():
    for text in ("", "   \n"):
        result = validate_output(text, max_chars=2000, pii_enabled=True)

        assert result.text == STEP_LIMIT_ANSWER
        assert not tuple(result.masked_types)


def test_long_answer_is_cut_to_the_maximum():
    cut = validate_output("a" * 30, max_chars=10, pii_enabled=True)
    exact = validate_output("b" * 10, max_chars=10, pii_enabled=True)

    assert cut.text == "a" * 10
    assert exact.text == "b" * 10


def test_personal_data_is_masked_before_the_answer_is_cut():
    result = validate_output(
        "Correo: ana.lopez@empresa.com", max_chars=15, pii_enabled=True
    )

    assert result.text == "Correo: [EMAIL]"
    assert tuple(result.masked_types) == ("email",)
