"""Validación de lo que entra al modelo y de lo que sale de él (ADR 0014).

La entrada con PII se bloquea con ``SensitiveDataError``; la salida se
valida con ``validate_output``: vacía se cambia por el mensaje de tope de
pasos, después se enmascara la PII y al final se recorta. Enmascarar antes de
recortar evita que quede medio dato visible.
"""

from dataclasses import dataclass
from typing import Sequence

from app.agent import STEP_LIMIT_ANSWER
from app.pii import mask

SENSITIVE_DATA_PREFIX = "sensitive data detected: "


class SensitiveDataError(Exception):
    """La pregunta o el historial contienen PII.

    El mensaje solo lleva los tipos, nunca los valores.

    :param types: Tipos de PII encontrados, en orden fijo
    :type types: Sequence[str]
    """

    def __init__(self, types: Sequence[str]) -> None:
        self.types = tuple(types)
        super().__init__(self.detail)

    @property
    def detail(self) -> str:
        """Texto del ``detail`` de la respuesta ``422``.

        :return: ``sensitive data detected: <tipos separados por coma>``
        :rtype: str
        """
        return SENSITIVE_DATA_PREFIX + ", ".join(self.types)


@dataclass(frozen=True)
class GuardedAnswer:
    """Respuesta del modelo ya validada.

    :param text: Texto final que se entrega
    :type text: str
    :param masked_types: Tipos de PII enmascarados (vacío si no hubo)
    :type masked_types: tuple[str, ...]
    """

    text: str
    masked_types: tuple[str, ...]


def validate_output(text: str, max_chars: int, pii_enabled: bool) -> GuardedAnswer:
    """Valida, enmascara y recorta la respuesta del modelo.

    :param text: Respuesta del agente
    :type text: str
    :param max_chars: Largo máximo (``OUTPUT_MAX_CHARS``)
    :type max_chars: int
    :param pii_enabled: Si se enmascara la PII (``PII_DETECTION``)
    :type pii_enabled: bool
    :return: Texto final y tipos enmascarados
    :rtype: GuardedAnswer
    """
    if not isinstance(text, str) or not text.strip():
        text = STEP_LIMIT_ANSWER
    masked_types: tuple[str, ...] = ()
    if pii_enabled:
        result = mask(text)
        text, masked_types = result.text, result.types
    return GuardedAnswer(text=text[:max_chars], masked_types=masked_types)
