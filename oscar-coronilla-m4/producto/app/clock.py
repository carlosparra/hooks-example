"""Reloj inyectable: el único lugar del producto que lee la hora real.

Las pruebas inyectan un reloj falso con la misma interfaz para que la hora de
los eventos y la latencia sean deterministas.
"""

import time
from datetime import datetime, timezone
from typing import Protocol


class Clock(Protocol):
    """Interfaz de reloj que usa el producto."""

    def now_utc(self) -> datetime:
        """Devuelve la hora actual con zona horaria UTC.

        :return: Hora actual en UTC
        :rtype: datetime.datetime
        """

    def monotonic(self) -> float:
        """Devuelve segundos de un reloj que nunca retrocede, para medir duraciones.

        :return: Segundos desde un origen arbitrario
        :rtype: float
        """


class SystemClock:
    """Reloj real del sistema operativo."""

    def now_utc(self) -> datetime:
        """Devuelve la hora actual del sistema en UTC.

        :return: Hora actual en UTC
        :rtype: datetime.datetime
        """
        return datetime.now(timezone.utc)

    def monotonic(self) -> float:
        """Devuelve el reloj monótono del sistema.

        :return: Segundos desde un origen arbitrario
        :rtype: float
        """
        return time.monotonic()
