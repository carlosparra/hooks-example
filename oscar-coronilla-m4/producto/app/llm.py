"""Interfaz de modelo de lenguaje, modelo simulado y fábrica de modelos."""

import json
import re
from typing import Iterable, Protocol, Sequence

import httpx

from app.config import FAKE_PROVIDER, GATEWAY_PROVIDER, Settings
from app.directory import normalize_text
from app.gateway import GatewayLanguageModel, build_http_client
from app.replies import Message, ModelReply, ModelUnavailableError

__all__ = [
    "FakeLanguageModel",
    "LanguageModel",
    "Message",
    "ModelReply",
    "ModelUnavailableError",
    "build_models",
]

TOOL_RESULT_PREFIX = "Resultado de la herramienta: "
HELP_ANSWER = "Pregúntame por un empleado (EMP-0001) o un departamento."
ANSWER_PREFIX = "Según el directorio: "
EMPLOYEE_ID_PATTERN = re.compile(r"\bEMP-\d{4}\b", re.IGNORECASE)
FAKE_MODEL_NAME = "fake"


class LanguageModel(Protocol):
    """Interfaz que cualquier modelo debe cumplir."""

    def complete(self, messages: Sequence[Message]) -> ModelReply:
        """Devuelve la respuesta del modelo para la conversación.

        :param messages: Mensajes con ``role`` y ``content``
        :type messages: Sequence[Mapping[str, str]]
        :return: Respuesta del modelo
        :rtype: ModelReply
        """


def count_words(text: str) -> int:
    """Cuenta palabras separadas por espacios.

    :param text: Texto a contar
    :type text: str
    :return: Número de palabras
    :rtype: int
    """
    return len(text.split())


class FakeLanguageModel:
    """Modelo simulado: decide con reglas sobre el último mensaje.

    Responde igual con cualquier nombre; el nombre solo sirve para cobrarlo con
    el precio del modelo real que simula.

    :param departments: Departamentos existentes en los datos
    :type departments: Iterable[str]
    :param name: Nombre del modelo que simula
    :type name: str
    """

    def __init__(
        self, departments: Iterable[str], name: str = FAKE_MODEL_NAME
    ) -> None:
        self.name = name
        self._departments = tuple(
            (name, re.compile(rf"\b{re.escape(normalize_text(name))}\b"))
            for name in departments
        )

    def complete(self, messages: Sequence[Message]) -> ModelReply:
        """Aplica las reglas y devuelve un único objeto JSON.

        :param messages: Mensajes con ``role`` y ``content``
        :type messages: Sequence[Mapping[str, str]]
        :return: Respuesta con conteo aproximado de tokens
        :rtype: ModelReply
        """
        last = str(messages[-1].get("content", "")) if messages else ""
        text = json.dumps(self._decide(last), ensure_ascii=False)
        input_tokens = sum(
            count_words(str(message.get("content", ""))) for message in messages
        )
        return ModelReply(
            text=text, input_tokens=input_tokens, output_tokens=count_words(text)
        )

    def _decide(self, content: str) -> dict:
        """Elige la respuesta según las reglas en orden de prioridad.

        :param content: Contenido del último mensaje
        :type content: str
        :return: Pedido de herramienta o respuesta
        :rtype: dict
        """
        if content.startswith(TOOL_RESULT_PREFIX):
            result = content[len(TOOL_RESULT_PREFIX):]
            return {"answer": f"{ANSWER_PREFIX}{result}"}
        match = EMPLOYEE_ID_PATTERN.search(content)
        if match:
            return {
                "tool": "get_employee",
                "args": {"employee_id": match.group(0).upper()},
            }
        department = self._find_department(content)
        if department:
            return {"tool": "search_by_department", "args": {"department": department}}
        return {"answer": HELP_ANSWER}

    def _find_department(self, content: str) -> str | None:
        """Busca un departamento mencionado como palabra completa.

        :param content: Texto donde buscar
        :type content: str
        :return: Nombre del departamento o ``None``
        :rtype: str | None
        """
        normalized = normalize_text(content)
        for name, pattern in self._departments:
            if pattern.search(normalized):
                return name
        return None


def build_models(
    settings: Settings,
    departments: Iterable[str],
    http_client: httpx.Client | None = None,
) -> dict[str, LanguageModel]:
    """Crea los dos modelos con nombre: el barato y el capaz.

    Con ``fake`` son dos modelos simulados que se llaman como ``MODEL_SMALL`` y
    ``MODEL_LARGE``. Con ``gateway`` comparten un cliente ``httpx``; solo se crea
    uno real si no se inyecta.

    :param settings: Configuración de la aplicación
    :type settings: Settings
    :param departments: Departamentos existentes, para el modelo simulado
    :type departments: Iterable[str]
    :param http_client: Cliente ``httpx.Client`` para el gateway, o ``None``
    :type http_client: httpx.Client | None
    :return: Modelos por nombre
    :rtype: dict[str, LanguageModel]
    :raises ValueError: Si el proveedor no está soportado
    """
    names = (settings.model_small, settings.model_large)
    if settings.model_provider == FAKE_PROVIDER:
        known = tuple(departments)
        return {name: FakeLanguageModel(known, name=name) for name in names}
    if settings.model_provider == GATEWAY_PROVIDER:
        client = http_client if http_client is not None else build_http_client()
        return {name: GatewayLanguageModel(name, settings, client) for name in names}
    raise ValueError(f"Unsupported MODEL_PROVIDER: {settings.model_provider!r}")
