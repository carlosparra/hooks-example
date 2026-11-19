"""Acceso por clave: una clave por cliente (ADR 0010).

``API_KEYS`` tiene la forma ``cliente:clave,cliente2:clave2``. Ningún mensaje de
error, evento ni ``repr`` de este módulo contiene el texto de una clave: los
errores dicen solo el número de la entrada y su largo.
"""

import hmac
import re
from dataclasses import dataclass, field
from typing import Annotated, Callable, Iterable

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from app.ratelimit import RateLimiter

API_KEY_HEADER = "X-API-Key"
INVALID_KEY_DETAIL = "invalid or missing API key"
INVALID_KEY_STATUS = 401
RATE_LIMITED_DETAIL = "rate limit exceeded"
RATE_LIMITED_STATUS = 429
RETRY_AFTER_HEADER = "Retry-After"
ENTRY_SEPARATOR = ","
CLIENT_SEPARATOR = ":"
# El nombre del cliente va al log: solo caracteres que no pueden inyectar texto.
CLIENT_NAME_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,64}")
# La clave viaja en un encabezado HTTP: solo ASCII visible, sin espacios.
KEY_PATTERN = re.compile(r"[\x21-\x7e]+")
KEY_ENCODING = "utf-8"


@dataclass(frozen=True)
class ApiKey:
    """Clave de un cliente.

    :param client: Nombre del cliente; va al log, a la auditoría y a la traza
    :type client: str
    :param key: Clave secreta; nunca aparece en ``repr``
    :type key: str
    """

    client: str
    key: str = field(repr=False)


def _entry_error(index: int, entry: str, reason: str) -> ValueError:
    """Crea el error de una entrada mal formada sin incluir su texto.

    :param index: Número de la entrada, empezando en 1
    :type index: int
    :param entry: Texto de la entrada; solo se usa su largo
    :type entry: str
    :param reason: Qué está mal, sin valores
    :type reason: str
    :return: Error con el número de la entrada y su largo
    :rtype: ValueError
    """
    return ValueError(
        f"API_KEYS entry {index} is malformed: {reason} "
        f"(entry length: {len(entry)} characters)"
    )


def _parse_entry(index: int, entry: str) -> ApiKey:
    """Convierte una entrada ``cliente:clave`` en ``ApiKey``.

    :param index: Número de la entrada, empezando en 1
    :type index: int
    :param entry: Texto de la entrada, ya sin espacios alrededor
    :type entry: str
    :return: Cliente y clave
    :rtype: ApiKey
    :raises ValueError: Si la entrada no tiene la forma ``cliente:clave``
    """
    client, separator, key = entry.partition(CLIENT_SEPARATOR)
    client, key = client.strip(), key.strip()
    if not separator:
        raise _entry_error(index, entry, "expected 'client:key'")
    if not CLIENT_NAME_PATTERN.fullmatch(client):
        raise _entry_error(
            index, entry, "client name must be 1 to 64 characters of [A-Za-z0-9._-]"
        )
    if not KEY_PATTERN.fullmatch(key):
        raise _entry_error(
            index, entry, "key must be non-empty printable ASCII without spaces"
        )
    return ApiKey(client=client, key=key)


def _check_unique(api_keys: Iterable[ApiKey], entries: list[str]) -> None:
    """Verifica que ningún cliente ni ninguna clave se repita.

    :param api_keys: Claves ya leídas, en el orden de las entradas
    :type api_keys: Iterable[ApiKey]
    :param entries: Textos de las entradas; solo se usa su largo
    :type entries: list[str]
    :raises ValueError: Si un cliente o una clave aparecen dos veces
    """
    clients: set[str] = set()
    keys: set[str] = set()
    for index, (api_key, entry) in enumerate(zip(api_keys, entries), start=1):
        if api_key.client in clients:
            raise _entry_error(index, entry, "client name is repeated")
        if api_key.key in keys:
            raise _entry_error(index, entry, "key is repeated")
        clients.add(api_key.client)
        keys.add(api_key.key)


def parse_api_keys(raw: str) -> tuple[ApiKey, ...]:
    """Lee ``API_KEYS`` (``cliente:clave,cliente2:clave2``).

    Ignora los espacios alrededor de cada parte. Un texto vacío no da ningún
    cliente.

    :param raw: Valor de ``API_KEYS``
    :type raw: str
    :return: Claves por cliente, en el orden en que aparecen
    :rtype: tuple[ApiKey, ...]
    :raises ValueError: Si alguna entrada está mal formada o se repite; el
        mensaje dice el número de la entrada y su largo, nunca su texto
    """
    if not raw.strip():
        return ()
    entries = [entry.strip() for entry in raw.split(ENTRY_SEPARATOR)]
    api_keys = tuple(
        _parse_entry(index, entry) for index, entry in enumerate(entries, start=1)
    )
    _check_unique(api_keys, entries)
    return api_keys


class ApiKeyAuth:
    """Identifica al cliente dueño de una clave.

    :param api_keys: Claves por cliente
    :type api_keys: Iterable[ApiKey]
    """

    def __init__(self, api_keys: Iterable[ApiKey]) -> None:
        self._keys = tuple(
            (api_key.client, api_key.key.encode(KEY_ENCODING)) for api_key in api_keys
        )

    def identify(self, candidate: str | None) -> str | None:
        """Devuelve el cliente dueño de la clave, o ``None``.

        Compara con ``hmac.compare_digest`` contra todas las claves, sin cortar
        al encontrar una, para no revelar por tiempos cuál se parece.

        :param candidate: Valor del encabezado ``X-API-Key`` o ``None``
        :type candidate: str | None
        :return: Nombre del cliente, o ``None`` si la clave falta o no coincide
        :rtype: str | None
        """
        if not candidate:
            return None
        encoded = candidate.encode(KEY_ENCODING)
        found = None
        for client, key in self._keys:
            if hmac.compare_digest(encoded, key):
                found = client
        return found


def build_require_client(
    auth: ApiKeyAuth, limiter: RateLimiter
) -> Callable[..., str]:
    """Crea la dependencia de FastAPI que exige clave y aplica el límite.

    La dependencia deja el cliente en ``request.state.client`` para el log.

    :param auth: Identificador de clientes
    :type auth: ApiKeyAuth
    :param limiter: Límite de peticiones por cliente
    :type limiter: RateLimiter
    :return: Dependencia que devuelve el nombre del cliente
    :rtype: Callable[..., str]
    """
    header_scheme = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)

    def require_client(
        request: Request,
        api_key: Annotated[str | None, Security(header_scheme)],
    ) -> str:
        """Responde ``401`` sin clave válida y ``429`` si el cliente se pasó.

        :param request: Petición en curso
        :type request: fastapi.Request
        :param api_key: Valor de ``X-API-Key`` o ``None``
        :type api_key: str | None
        :return: Nombre del cliente
        :rtype: str
        :raises fastapi.HTTPException: ``401`` o ``429`` con ``Retry-After``
        """
        client = auth.identify(api_key)
        if client is None:
            raise HTTPException(
                status_code=INVALID_KEY_STATUS, detail=INVALID_KEY_DETAIL
            )
        request.state.client = client
        decision = limiter.check(client)
        if not decision.allowed:
            raise HTTPException(
                status_code=RATE_LIMITED_STATUS,
                detail=RATE_LIMITED_DETAIL,
                headers={RETRY_AFTER_HEADER: str(decision.retry_after)},
            )
        return client

    return require_client
