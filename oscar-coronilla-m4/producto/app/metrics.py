"""Métricas en memoria de este proceso, solo para diagnóstico (ADR 0005).

Los percentiles usan el método de rango más cercano sobre una ventana acotada de
latencias recientes; solo las respuestas ``5xx`` cuentan como error.
"""

import math
import os
import threading
from collections import deque
from typing import Any, Iterable

DEFAULT_WINDOW = 1000
SERVER_ERROR_STATUS = 500


def nearest_rank(values: Iterable[float], percentile: float) -> float:
    """Calcula un percentil por el método de rango más cercano.

    :param values: Valores observados
    :type values: Iterable[float]
    :param percentile: Percentil entre 0 y 100
    :type percentile: float
    :return: El valor del percentil, o 0 si no hay valores
    :rtype: float
    """
    ordered = sorted(values)
    if not ordered:
        return 0
    rank = max(1, math.ceil(percentile / 100 * len(ordered)))
    return ordered[rank - 1]


# Un contador por métrica publicada: agruparlos ocultaría qué mide cada uno.
class Metrics:  # pylint: disable=too-many-instance-attributes
    """Contadores del proceso protegidos con un candado.

    :param window: Cuántas latencias recientes se guardan para los percentiles
    :type window: int
    """

    def __init__(self, window: int = DEFAULT_WINDOW) -> None:
        self._lock = threading.Lock()
        self._latencies: deque[float] = deque(maxlen=window)
        self._requests = 0
        self._errors = 0
        self._input_tokens = 0
        self._output_tokens = 0
        self._cost_usd = 0.0
        self._pii_blocked = 0
        self._pii_masked = 0

    def record_request(self, latency_ms: float, status: int) -> None:
        """Registra una petición terminada.

        :param latency_ms: Duración de la petición en milisegundos
        :type latency_ms: float
        :param status: Código HTTP de la respuesta
        :type status: int
        """
        with self._lock:
            self._requests += 1
            if status >= SERVER_ERROR_STATUS:
                self._errors += 1
            self._latencies.append(latency_ms)

    def add_tokens(self, input_tokens: int, output_tokens: int) -> None:
        """Suma los tokens de una corrida del agente.

        :param input_tokens: Tokens de entrada
        :type input_tokens: int
        :param output_tokens: Tokens de salida
        :type output_tokens: int
        """
        with self._lock:
            self._input_tokens += input_tokens
            self._output_tokens += output_tokens

    def add_cost(self, cost_usd: float) -> None:
        """Suma el costo de una respuesta.

        :param cost_usd: Costo en USD de la respuesta
        :type cost_usd: float
        """
        with self._lock:
            self._cost_usd += cost_usd

    def cost_usd(self) -> float:
        """Devuelve el costo acumulado del proceso.

        Va aparte de ``snapshot`` para no cambiar la forma de las métricas de la
        sesión 2; ``GET /metrics`` junta ambos.

        :return: Costo acumulado en USD
        :rtype: float
        """
        with self._lock:
            return self._cost_usd

    def add_pii_blocked(self) -> None:
        """Cuenta una pregunta bloqueada por PII en la entrada."""
        with self._lock:
            self._pii_blocked += 1

    def add_pii_masked(self) -> None:
        """Cuenta una respuesta con PII enmascarada en la salida."""
        with self._lock:
            self._pii_masked += 1

    def pii_counts(self) -> dict[str, int]:
        """Devuelve los contadores de PII del proceso.

        Va aparte de ``snapshot`` para no cambiar la forma de las métricas de la
        sesión 2; ``GET /metrics`` los junta.

        :return: ``pii_blocked`` y ``pii_masked``
        :rtype: dict[str, int]
        """
        with self._lock:
            return {"pii_blocked": self._pii_blocked, "pii_masked": self._pii_masked}

    def snapshot(self, slo_p95_ms: int) -> dict[str, Any]:
        """Arma la respuesta de ``GET /metrics``.

        :param slo_p95_ms: Meta de latencia p95 en milisegundos
        :type slo_p95_ms: int
        :return: Proceso, peticiones, tasa de error, latencias, tokens y SLO
        :rtype: dict[str, Any]
        """
        with self._lock:
            latencies = list(self._latencies)
            requests = self._requests
            errors = self._errors
            tokens = {"input": self._input_tokens, "output": self._output_tokens}
        p95 = nearest_rank(latencies, 95)
        return {
            "pid": os.getpid(),
            "requests": requests,
            "error_rate": errors / requests if requests else 0,
            "latency_ms": {"p50": nearest_rank(latencies, 50), "p95": p95},
            "tokens": tokens,
            "slo": {"p95_ms_target": slo_p95_ms, "met": p95 < slo_p95_ms},
        }
