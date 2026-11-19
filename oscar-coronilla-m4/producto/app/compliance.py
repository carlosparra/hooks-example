"""Reglas de compliance revisadas al arrancar (ADR 0012).

Con ``ENVIRONMENT=production`` el producto se niega a arrancar si la
configuración no es segura. Los mensajes nombran la regla, nunca un valor.
"""

from app.config import FAKE_PROVIDER, PRODUCTION_ENVIRONMENT, Settings

MIN_API_KEY_LENGTH = 16
RULE_REAL_MODEL = "MODEL_PROVIDER must not be 'fake' in production"
RULE_KEYS_PRESENT = "API_KEYS must not be empty in production"
RULE_TRACES_HIDDEN = (
    "HIDE_INPUTS and HIDE_OUTPUTS must be 'true' when LANGSMITH_TRACING is on "
    "in production"
)
RULE_PII_ON = "PII_DETECTION must be 'true' in production"


def _short_keys_rule(count: int) -> str:
    """Describe la regla del largo mínimo de las claves, sin mostrarlas.

    :param count: Cuántas claves son más cortas que el mínimo
    :type count: int
    :return: Texto de la regla violada
    :rtype: str
    """
    return (
        f"every API key must have at least {MIN_API_KEY_LENGTH} characters in "
        f"production ({count} shorter)"
    )


def violations(settings: Settings) -> list[str]:
    """Lista las reglas de producción que la configuración no cumple.

    Fuera de ``production`` no exige nada. Las trazas se consideran pedidas con
    ``LANGSMITH_TRACING=true``, aunque falte la clave de LangSmith.

    :param settings: Configuración validada
    :type settings: Settings
    :return: Una entrada por regla violada; vacía si todo está bien
    :rtype: list[str]
    """
    if settings.environment != PRODUCTION_ENVIRONMENT:
        return []
    found = []
    if settings.model_provider == FAKE_PROVIDER:
        found.append(RULE_REAL_MODEL)
    if not settings.api_keys:
        found.append(RULE_KEYS_PRESENT)
    short = sum(
        1 for api_key in settings.api_keys if len(api_key.key) < MIN_API_KEY_LENGTH
    )
    if short:
        found.append(_short_keys_rule(short))
    if settings.langsmith_tracing and not (
        settings.hide_inputs and settings.hide_outputs
    ):
        found.append(RULE_TRACES_HIDDEN)
    if not settings.pii_detection:
        found.append(RULE_PII_ON)
    return found


class ComplianceError(ValueError):
    """La configuración de producción viola alguna regla de compliance."""


def enforce(settings: Settings) -> None:
    """Impide arrancar si la configuración viola alguna regla.

    :param settings: Configuración validada
    :type settings: Settings
    :raises ComplianceError: Con los nombres de las reglas violadas
    """
    found = violations(settings)
    if found:
        raise ComplianceError(
            "production configuration is not compliant: " + "; ".join(found)
        )
