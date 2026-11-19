"""Trazas opcionales en LangSmith (ADR 0006).

Sin ``LANGSMITH_TRACING=true`` y ``LANGSMITH_API_KEY`` se usa ``NoopTracer``: no
se importa ``langsmith``, no se crea cliente y no se abre ninguna conexión. La
clave la lee ``langsmith`` del entorno; este módulo nunca la ve.
"""

from typing import Any, Callable, Protocol, Sequence, TypeVar

from app.config import Settings

Func = TypeVar("Func", bound=Callable[..., Any])
Traceable = Callable[..., Callable[[Func], Func]]


def hide_payload(_payload: Any) -> dict[str, Any]:
    """Reemplaza entradas o salidas por un objeto vacío antes de enviarlas.

    :param _payload: Entradas o salidas originales (se descartan)
    :type _payload: Any
    :return: Objeto vacío
    :rtype: dict[str, Any]
    """
    return {}


def keep_payload(payload: Any) -> Any:
    """Deja pasar entradas o salidas sin cambios.

    :param payload: Entradas o salidas originales
    :type payload: Any
    :return: El mismo valor
    :rtype: Any
    """
    return payload


class Tracer(Protocol):
    """Interfaz para envolver funciones en trazas."""

    # Un argumento por metadato: agruparlos rompería la firma de las sesiones previas.
    def wrap(  # pylint: disable=too-many-arguments
        self,
        func: Func,
        *,
        name: str,
        run_type: str,
        request_id: str,
        client: str | None = None,
        pii_types: Sequence[str] | None = None,
    ) -> Func:
        """Envuelve ``func`` para que cada llamada quede como traza.

        :param func: Función a envolver
        :type func: Callable
        :param name: Nombre de la traza
        :type name: str
        :param run_type: Tipo de traza (``chain``, ``llm``, ``tool``)
        :type run_type: str
        :param request_id: Id de la petición, va en los metadatos
        :type request_id: str
        :param client: Nombre del cliente, va en los metadatos (nunca la clave)
        :type client: str | None
        :param pii_types: Tipos de PII detectados, van en los metadatos (nunca
            los valores)
        :type pii_types: Sequence[str] | None
        :return: Función envuelta
        :rtype: Callable
        """


class NoopTracer:
    """Tracer apagado: devuelve la misma función."""

    def wrap(  # pylint: disable=too-many-arguments
        self,
        func: Func,
        *,
        name: str,
        run_type: str,
        request_id: str,
        client: str | None = None,
        pii_types: Sequence[str] | None = None,
    ) -> Func:
        """Devuelve ``func`` sin cambios.

        :param func: Función a envolver
        :type func: Callable
        :param name: Nombre de la traza (se ignora)
        :type name: str
        :param run_type: Tipo de traza (se ignora)
        :type run_type: str
        :param request_id: Id de la petición (se ignora)
        :type request_id: str
        :param client: Nombre del cliente (se ignora)
        :type client: str | None
        :param pii_types: Tipos de PII (se ignoran)
        :type pii_types: Sequence[str] | None
        :return: La misma función
        :rtype: Callable
        """
        del name, run_type, request_id, client, pii_types
        return func


class LangSmithTracer:
    """Tracer que aplica ``traceable`` de LangSmith.

    :param traceable: Fábrica de decoradores con la firma de ``langsmith.traceable``
    :type traceable: Callable
    :param hide_inputs: Si es verdadero, no se envían las entradas
    :type hide_inputs: bool
    :param hide_outputs: Si es verdadero, no se envían las salidas
    :type hide_outputs: bool
    """

    def __init__(
        self, traceable: Traceable, hide_inputs: bool, hide_outputs: bool
    ) -> None:
        self._traceable = traceable
        self._process_inputs = hide_payload if hide_inputs else keep_payload
        self._process_outputs = hide_payload if hide_outputs else keep_payload

    def wrap(  # pylint: disable=too-many-arguments
        self,
        func: Func,
        *,
        name: str,
        run_type: str,
        request_id: str,
        client: str | None = None,
        pii_types: Sequence[str] | None = None,
    ) -> Func:
        """Envuelve ``func`` con ``traceable`` y el ``request_id`` en metadatos.

        Si hay cliente, su nombre también va en los metadatos; la clave nunca.
        Si hay tipos de PII, van en ``pii_types``; los valores nunca.

        :param func: Función a envolver
        :type func: Callable
        :param name: Nombre de la traza
        :type name: str
        :param run_type: Tipo de traza (``chain``, ``llm``, ``tool``)
        :type run_type: str
        :param request_id: Id de la petición
        :type request_id: str
        :param client: Nombre del cliente o ``None``
        :type client: str | None
        :param pii_types: Tipos de PII detectados o ``None``
        :type pii_types: Sequence[str] | None
        :return: Función envuelta
        :rtype: Callable
        """
        metadata: dict[str, Any] = {"request_id": request_id}
        if client is not None:
            metadata["client"] = client
        if pii_types is not None:
            metadata["pii_types"] = list(pii_types)
        decorator = self._traceable(
            run_type=run_type,
            name=name,
            metadata=metadata,
            process_inputs=self._process_inputs,
            process_outputs=self._process_outputs,
        )
        return decorator(func)


def _load_traceable() -> Traceable:
    """Importa ``langsmith.traceable`` solo cuando las trazas están encendidas.

    :return: El decorador de LangSmith
    :rtype: Callable
    """
    # Import diferido: sin trazas no se carga langsmith ni se toca la red.
    from langsmith import traceable  # pylint: disable=import-outside-toplevel

    return traceable


def build_tracer(settings: Settings, traceable: Traceable | None = None) -> Tracer:
    """Crea el tracer que indica la configuración.

    :param settings: Configuración de la aplicación
    :type settings: Settings
    :param traceable: Decorador a usar; si falta, el de ``langsmith``
    :type traceable: Callable | None
    :return: ``LangSmithTracer`` si las trazas están encendidas; si no,
        ``NoopTracer``
    :rtype: Tracer
    """
    if not settings.tracing_enabled:
        return NoopTracer()
    return LangSmithTracer(
        traceable=traceable or _load_traceable(),
        hide_inputs=settings.hide_inputs,
        hide_outputs=settings.hide_outputs,
    )
