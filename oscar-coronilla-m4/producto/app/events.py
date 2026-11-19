"""Log estructurado: una línea JSON por evento.

Cada línea lleva ``ts`` (ISO 8601 en UTC), ``service``, ``event`` y
``request_id``, más los campos propios del evento. Quien emite un evento es
responsable de no pasar textos personales (preguntas, respuestas, mensajes de
error) ni claves.
"""

import json
import sys
import threading
from datetime import timezone
from typing import Any, TextIO

from app.clock import Clock


class EventLogger:
    """Escribe eventos como líneas JSON en un flujo de texto.

    :param stream: Flujo de salida; si es ``None`` se usa la salida estándar
        vigente al momento de escribir
    :type stream: TextIO | None
    :param clock: Reloj que da la hora de cada evento
    :type clock: Clock
    :param service: Nombre del servicio, campo ``service``
    :type service: str
    """

    def __init__(self, stream: TextIO | None, clock: Clock, service: str) -> None:
        self._stream = stream
        self._clock = clock
        self._service = service
        self._lock = threading.Lock()

    def emit(self, event: str, request_id: str, **fields: Any) -> None:
        """Escribe un evento en una sola línea.

        :param event: Nombre del evento (``request``, ``agent_run``, ``audit``...)
        :type event: str
        :param request_id: Id de la petición a la que pertenece el evento
        :type request_id: str
        :param fields: Campos propios del evento; deben ser serializables
        :type fields: Any
        """
        record = {
            "ts": self._timestamp(),
            "service": self._service,
            "event": event,
            "request_id": request_id,
            **fields,
        }
        line = json.dumps(record, ensure_ascii=False, default=str)
        stream = self._stream if self._stream is not None else sys.stdout
        with self._lock:
            stream.write(line + "\n")
            stream.flush()

    def _timestamp(self) -> str:
        """Formatea la hora del reloj como ISO 8601 en UTC con sufijo ``Z``.

        :return: Hora del evento
        :rtype: str
        """
        now = self._clock.now_utc().astimezone(timezone.utc)
        return now.isoformat(timespec="milliseconds").replace("+00:00", "Z")
