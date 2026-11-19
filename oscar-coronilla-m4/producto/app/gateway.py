"""Modelo real: Cloudflare Workers AI a través de AI Gateway (ADR 0008).

El cliente ``httpx`` se inyecta, así que las pruebas usan ``MockTransport`` y
nunca tocan la red. Ningún mensaje de error lleva el token, la cuenta ni el
cuerpo de la respuesta del proveedor.
"""

import json
import re
from typing import Any, Sequence

import httpx

from app.config import Settings
from app.replies import Message, ModelReply, ModelUnavailableError

GATEWAY_URL = (
    "https://gateway.ai.cloudflare.com/v1/{account_id}/{gateway_id}"
    "/workers-ai/v1/chat/completions"
)
HTTP_TIMEOUT_SECONDS = 30.0
CACHE_TTL_HEADER = "cf-aig-cache-ttl"
AIG_AUTH_HEADER = "cf-aig-authorization"
CACHE_STATUS_HEADER = "cf-aig-cache-status"
CACHE_HIT = "HIT"
CODE_FENCE_PATTERN = re.compile(r"^```[a-zA-Z]*\s*(.*?)\s*```$", re.DOTALL)
SYSTEM_PROMPT = (
    "Eres el asistente de Recursos Humanos. Responde siempre con un único objeto "
    "JSON y nada más. Para consultar datos pide una herramienta: "
    '{"tool": "get_employee", "args": {"employee_id": "EMP-0001"}} o '
    '{"tool": "search_by_department", "args": {"department": "Ventas"}}. '
    'Cuando tengas la respuesta, devuelve {"answer": "texto en español"}. '
    "Usa solo los datos que devuelven las herramientas."
)


def build_http_client() -> httpx.Client:
    """Crea el cliente HTTP real para el gateway, con tiempo máximo de espera.

    :return: Cliente ``httpx`` listo para usar
    :rtype: httpx.Client
    """
    return httpx.Client(timeout=HTTP_TIMEOUT_SECONDS)


def normalize_content(content: Any) -> str:
    """Convierte el contenido del modelo en el texto JSON del protocolo.

    Acepta un objeto ya decodificado, un bloque de código o un texto con el
    objeto JSON dentro. Si no encuentra un objeto válido devuelve el texto tal
    cual: el agente ya tolera respuestas que no son JSON (ADR 0002).

    :param content: Contenido de ``choices[0].message.content``
    :type content: Any
    :return: Texto que el agente puede interpretar
    :rtype: str
    """
    if isinstance(content, (dict, list)):
        return json.dumps(content, ensure_ascii=False)
    text = "" if content is None else str(content).strip()
    fenced = CODE_FENCE_PATTERN.match(text)
    if fenced:
        text = fenced.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        candidate = text[start : end + 1]
        try:
            json.loads(candidate)
        except ValueError:
            return text
        return candidate
    return text


def _read_tokens(usage: Any) -> tuple[int, int]:
    """Lee los tokens de entrada y salida del bloque ``usage``.

    :param usage: Valor de ``usage`` en la respuesta del gateway
    :type usage: Any
    :return: ``(prompt_tokens, completion_tokens)``
    :rtype: tuple[int, int]
    :raises ModelUnavailableError: Si faltan o no son enteros no negativos
    """
    if not isinstance(usage, dict):
        raise ModelUnavailableError("gateway response has no usage")
    tokens = (usage.get("prompt_tokens"), usage.get("completion_tokens"))
    for value in tokens:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ModelUnavailableError("gateway response has invalid usage")
    return tokens[0], tokens[1]


def _read_content(data: Any) -> Any:
    """Lee ``choices[0].message.content`` de la respuesta del gateway.

    :param data: Cuerpo JSON de la respuesta
    :type data: Any
    :return: Contenido devuelto por el modelo
    :rtype: Any
    :raises ModelUnavailableError: Si la respuesta no tiene esa forma
    """
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise ModelUnavailableError("gateway response has no message") from error


class GatewayLanguageModel:
    """Modelo de Workers AI detrás de AI Gateway; cumple ``LanguageModel``.

    :param name: Nombre del modelo en Workers AI (por ejemplo ``@cf/...``)
    :type name: str
    :param settings: Configuración con las variables ``CF_*`` y las palancas
    :type settings: Settings
    :param client: Cliente ``httpx`` inyectado
    :type client: httpx.Client
    """

    def __init__(self, name: str, settings: Settings, client: httpx.Client) -> None:
        self.name = name
        self._settings = settings
        self._client = client
        self._url = GATEWAY_URL.format(
            account_id=settings.cf_account_id, gateway_id=settings.cf_gateway_id
        )

    def complete(self, messages: Sequence[Message]) -> ModelReply:
        """Manda la conversación al gateway y lee respuesta, tokens y caché.

        :param messages: Mensajes con ``role`` y ``content``
        :type messages: Sequence[Mapping[str, str]]
        :return: Respuesta normalizada a JSON, tokens y si vino de la caché
        :rtype: ModelReply
        :raises ModelUnavailableError: Si la llamada falla o la respuesta no se
            puede leer
        """
        response = self._post(messages)
        try:
            data = response.json()
        except ValueError as error:
            raise ModelUnavailableError("gateway response is not JSON") from error
        content = _read_content(data)
        input_tokens, output_tokens = _read_tokens(data.get("usage"))
        cache_status = response.headers.get(CACHE_STATUS_HEADER, "")
        return ModelReply(
            text=normalize_content(content),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached=cache_status.strip().upper() == CACHE_HIT,
        )

    def _post(self, messages: Sequence[Message]) -> httpx.Response:
        """Hace el ``POST`` al gateway y revisa el código de estado.

        :param messages: Mensajes con ``role`` y ``content``
        :type messages: Sequence[Mapping[str, str]]
        :return: Respuesta HTTP con estado 2xx
        :rtype: httpx.Response
        :raises ModelUnavailableError: Si hay error de red, tiempo agotado o un
            estado que no es 2xx
        """
        body = {
            "model": self.name,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}]
            + [dict(message) for message in messages],
            "max_tokens": self._settings.model_max_tokens,
            "temperature": self._settings.model_temperature,
        }
        try:
            response = self._client.post(
                self._url, json=body, headers=self._headers()
            )
        except httpx.HTTPError as error:
            raise ModelUnavailableError(
                f"gateway request failed: {type(error).__name__}"
            ) from None
        if not response.is_success:
            raise ModelUnavailableError(
                f"gateway returned status {response.status_code}"
            )
        return response

    def _headers(self) -> dict[str, str]:
        """Arma los encabezados: autorización, gateway autenticado y caché.

        ``cf-aig-authorization`` solo se manda si ``CF_AIG_TOKEN`` tiene valor.

        :return: Encabezados de la petición
        :rtype: dict[str, str]
        """
        headers = {"Authorization": f"Bearer {self._settings.cf_api_token}"}
        if self._settings.cf_aig_token:
            headers[AIG_AUTH_HEADER] = f"Bearer {self._settings.cf_aig_token}"
        if self._settings.cache_ttl_seconds > 0:
            headers[CACHE_TTL_HEADER] = str(self._settings.cache_ttl_seconds)
        return headers
