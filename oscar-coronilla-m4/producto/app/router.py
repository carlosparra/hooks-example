"""Enrutador por regla: elige el modelo de cada pregunta sin usar otro modelo.

ADR 0007. La regla se evalúa en orden y la primera que aplica gana.
"""

from dataclasses import dataclass

from app.config import Settings
from app.directory import normalize_text

LARGE_MODEL_KEYWORDS = ("compara", "resume", "explica", "por que", "analiza", "todos")
REASON_ROUTING_OFF = "routing_off"
REASON_LONG_QUESTION = "long_question"
REASON_KEYWORD = "keyword"
REASON_SHORT_QUESTION = "short_question"


@dataclass(frozen=True)
class Route:
    """Modelo elegido y el motivo de la elección.

    :param model: Nombre del modelo
    :type model: str
    :param reason: Motivo: ``routing_off``, ``long_question``, ``keyword`` o
        ``short_question``
    :type reason: str
    """

    model: str
    reason: str


def route(question: str, settings: Settings) -> Route:
    """Elige el modelo para una pregunta.

    - ``ROUTING=false``: modelo capaz.
    - Más de ``ROUTER_MAX_CHARS`` caracteres: modelo capaz.
    - Contiene una palabra clave (sin acentos ni mayúsculas): modelo capaz.
    - En cualquier otro caso: modelo barato.

    :param question: Pregunta ya validada
    :type question: str
    :param settings: Configuración con los modelos y la regla
    :type settings: Settings
    :return: Modelo y motivo
    :rtype: Route
    """
    if not settings.routing:
        return Route(settings.model_large, REASON_ROUTING_OFF)
    if len(question) > settings.router_max_chars:
        return Route(settings.model_large, REASON_LONG_QUESTION)
    normalized = normalize_text(question)
    if any(keyword in normalized for keyword in LARGE_MODEL_KEYWORDS):
        return Route(settings.model_large, REASON_KEYWORD)
    return Route(settings.model_small, REASON_SHORT_QUESTION)
