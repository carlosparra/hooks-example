"""Límite de peticiones por cliente, en memoria del proceso (ADR 0011).

Ventana deslizante: por cada cliente se guardan las marcas del reloj inyectado
de las peticiones aceptadas en los últimos ``window_seconds`` segundos.
"""

import math
import threading
from collections import deque
from dataclasses import dataclass

from app.clock import Clock

DEFAULT_WINDOW_SECONDS = 60.0
MIN_RETRY_AFTER_SECONDS = 1


@dataclass(frozen=True)
class Decision:
    """Resultado de revisar el límite.

    :param allowed: Si la petición puede seguir
    :type allowed: bool
    :param retry_after: Segundos enteros que faltan para poder reintentar
        (1 o más si se niega; 0 si se acepta)
    :type retry_after: int
    """

    allowed: bool
    retry_after: int = 0


class RateLimiter:
    """Cuenta las peticiones de cada cliente en una ventana deslizante.

    :param limit: Peticiones permitidas por ventana
    :type limit: int
    :param clock: Reloj inyectado; se usa ``monotonic()``
    :type clock: Clock
    :param window_seconds: Largo de la ventana en segundos
    :type window_seconds: float
    :raises ValueError: Si ``limit`` o ``window_seconds`` no son positivos
    """

    def __init__(
        self,
        limit: int,
        clock: Clock,
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
    ) -> None:
        if limit < 1:
            raise ValueError(f"rate limit must be at least 1, got {limit!r}")
        if window_seconds <= 0:
            raise ValueError(
                f"rate limit window must be positive, got {window_seconds!r}"
            )
        self._limit = limit
        self._clock = clock
        self._window = window_seconds
        self._marks: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, client: str) -> Decision:
        """Revisa el límite del cliente y, si lo acepta, anota la petición.

        :param client: Nombre del cliente ya autenticado
        :type client: str
        :return: Si se acepta y, si no, cuántos segundos esperar
        :rtype: Decision
        """
        now = self._clock.monotonic()
        with self._lock:
            marks = self._marks.setdefault(client, deque())
            while marks and now - marks[0] >= self._window:
                marks.popleft()
            if len(marks) >= self._limit:
                remaining = self._window - (now - marks[0])
                retry_after = max(MIN_RETRY_AFTER_SECONDS, math.ceil(remaining))
                return Decision(allowed=False, retry_after=retry_after)
            marks.append(now)
            return Decision(allowed=True)
