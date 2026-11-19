"""Middleware ASGI de observabilidad (ADR 0004).

Para cada petición HTTP fija el ``request_id``, mide la latencia con el reloj
inyectado, escribe los eventos ``request`` y ``error``, alimenta ``Metrics``,
convierte cualquier excepción en ``500`` y agrega el encabezado ``X-Request-ID``.
"""

import re
import uuid
from typing import Any, Awaitable, Callable, MutableMapping

from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse

from app.clock import Clock
from app.events import EventLogger
from app.metrics import Metrics

REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._:-]{1,128}")
INTERNAL_ERROR_DETAIL = "internal error"
MILLISECONDS = 1000

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
AsgiApp = Callable[[Scope, Receive, Send], Awaitable[None]]


def new_request_id() -> str:
    """Genera un id de petición nuevo.

    :return: UUID versión 4 en texto
    :rtype: str
    """
    return str(uuid.uuid4())


def resolve_request_id(
    candidate: str | None, factory: Callable[[], str] = new_request_id
) -> str:
    """Usa el id del cliente si es válido; si no, genera uno.

    Solo se aceptan de 1 a 128 caracteres de ``[A-Za-z0-9._:-]``, para que el id
    no pueda inyectar texto en el log.

    :param candidate: Valor del encabezado ``X-Request-ID`` o ``None``
    :type candidate: str | None
    :param factory: Generador de ids nuevos
    :type factory: Callable[[], str]
    :return: Id de la petición
    :rtype: str
    """
    if candidate is not None and REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return factory()


def read_header(scope: Scope, name: str) -> str | None:
    """Lee un encabezado de la petición sin distinguir mayúsculas.

    :param scope: Scope ASGI de la petición
    :type scope: MutableMapping[str, Any]
    :param name: Nombre del encabezado
    :type name: str
    :return: Valor del primer encabezado con ese nombre o ``None``
    :rtype: str | None
    """
    wanted = name.lower().encode("latin-1")
    for key, value in scope.get("headers", []):
        if key.lower() == wanted:
            return value.decode("latin-1")
    return None


class ObservabilityMiddleware:
    """Middleware ASGI que hace rastreable y medible cada petición.

    :param app: Aplicación ASGI envuelta
    :type app: Callable
    :param events: Log de eventos JSON
    :type events: EventLogger
    :param metrics: Métricas del proceso
    :type metrics: Metrics
    :param clock: Reloj para medir la latencia
    :type clock: Clock
    :param id_factory: Generador de ids nuevos
    :type id_factory: Callable[[], str]
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        app: AsgiApp,
        *,
        events: EventLogger,
        metrics: Metrics,
        clock: Clock,
        id_factory: Callable[[], str] = new_request_id,
    ) -> None:
        self._app = app
        self._events = events
        self._metrics = metrics
        self._clock = clock
        self._id_factory = id_factory

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Atiende una petición ASGI.

        :param scope: Scope ASGI
        :type scope: MutableMapping[str, Any]
        :param receive: Canal de entrada ASGI
        :type receive: Callable
        :param send: Canal de salida ASGI
        :type send: Callable
        """
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        request_id = resolve_request_id(
            read_header(scope, REQUEST_ID_HEADER), self._id_factory
        )
        scope.setdefault("state", {})["request_id"] = request_id
        started = self._clock.monotonic()
        outcome = {"status": 500, "started": False}

        async def send_with_id(message: Message) -> None:
            """Agrega el encabezado del id y anota el código de respuesta."""
            if message["type"] == "http.response.start":
                outcome["status"] = message["status"]
                outcome["started"] = True
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self._app(scope, receive, send_with_id)
        # Cualquier fallo debe terminar en un 500 con su request_id y su evento.
        except Exception as error:  # pylint: disable=broad-exception-caught
            self._events.emit("error", request_id, error_type=type(error).__name__)
            if outcome["started"]:
                raise
            response = JSONResponse(
                {"detail": INTERNAL_ERROR_DETAIL, "request_id": request_id},
                status_code=500,
            )
            await response(scope, receive, send_with_id)
        finally:
            self._record(scope, request_id, int(outcome["status"]), started)

    def _record(
        self, scope: Scope, request_id: str, status: int, started: float
    ) -> None:
        """Escribe el evento ``request`` y lo suma a las métricas.

        ``client`` sale de ``scope["state"]`` (lo deja la dependencia de la
        clave); es ``None`` si la petición no traía una clave válida. Nunca se
        registran los encabezados.

        :param scope: Scope ASGI de la petición
        :type scope: MutableMapping[str, Any]
        :param request_id: Id de la petición
        :type request_id: str
        :param status: Código HTTP de la respuesta
        :type status: int
        :param started: Lectura del reloj monótono al empezar
        :type started: float
        """
        latency_ms = round((self._clock.monotonic() - started) * MILLISECONDS, 3)
        self._events.emit(
            "request",
            request_id,
            method=scope.get("method"),
            path=scope.get("path"),
            status=status,
            latency_ms=latency_ms,
            client=scope.get("state", {}).get("client"),
        )
        self._metrics.record_request(latency_ms=latency_ms, status=status)
