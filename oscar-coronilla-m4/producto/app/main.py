"""API web del HR Assistant.

``create_app()`` recibe sus dependencias para que las pruebas inyecten las suyas.
El módulo expone ``app`` construida con la configuración del entorno.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Callable, Literal, Mapping, Sequence, TextIO

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator

from app.agent import Agent, AgentResult
from app.clock import Clock, SystemClock
from app.compliance import enforce
from app.config import Settings
from app.directory import EmployeeDirectory
from app.events import EventLogger
from app.guardrails import SensitiveDataError, validate_output
from app.llm import LanguageModel, ModelUnavailableError, build_models
from app.metrics import Metrics
from app.middleware import ObservabilityMiddleware
from app.pii import detect_all
from app.pricing import PriceTable
from app.ratelimit import RateLimiter
from app.router import route
from app.security import ApiKeyAuth, build_require_client
from app.tracing import Tracer, build_tracer

PAGE_PATH = Path(__file__).resolve().parent / "static" / "index.html"
MODEL_UNAVAILABLE_DETAIL = "model unavailable"
MODEL_UNAVAILABLE_STATUS = 502
SENSITIVE_DATA_STATUS = 422
PII_INPUT = "input"
PII_OUTPUT = "output"


def report_pii_types(types: Sequence[str]) -> list[str]:
    """Tramo de traza de una detección: su única entrada son los tipos.

    :param types: Tipos de PII detectados (nunca los valores)
    :type types: Sequence[str]
    :return: Los mismos tipos, como lista
    :rtype: list[str]
    """
    return list(types)


def window_history(history: Sequence[Any], size: int) -> list[Any]:
    """Devuelve los últimos ``size`` mensajes del historial.

    Con 0 no manda ninguno: ``history[-0:]`` devolvería todo.

    :param history: Mensajes previos de la conversación
    :type history: Sequence[Any]
    :param size: Cuántos mensajes conservar (``HISTORY_WINDOW``)
    :type size: int
    :return: Los últimos mensajes, en orden
    :rtype: list[Any]
    """
    if size <= 0:
        return []
    return list(history[-size:])


@dataclass(frozen=True)
class CostControls:
    """Lo que necesita el servicio para elegir el modelo y cobrar la respuesta.

    :param settings: Configuración con la regla de ruta y la ventana
    :type settings: Settings
    :param models: Modelos por nombre (``MODEL_SMALL`` y ``MODEL_LARGE``)
    :type models: Mapping[str, LanguageModel]
    :param prices: Tabla de precios por modelo
    :type prices: PriceTable
    """

    settings: Settings
    models: Mapping[str, LanguageModel]
    prices: PriceTable


class HistoryMessage(BaseModel):
    """Mensaje previo de la conversación, enviado por el cliente.

    :param role: ``user`` o ``assistant``
    :type role: str
    :param content: Texto del mensaje
    :type content: str
    """

    role: Literal["user", "assistant"]
    content: str


class AskResponse(BaseModel):
    """Respuesta de ``POST /ask``.

    :param answer: Respuesta en español
    :type answer: str
    :param steps: Vueltas del bucle del agente
    :type steps: int
    :param tools_used: Herramientas usadas
    :type tools_used: list[str]
    :param input_tokens: Tokens de entrada sumados
    :type input_tokens: int
    :param output_tokens: Tokens de salida sumados
    :type output_tokens: int
    :param request_id: Id de la petición, para pasarlo a soporte
    :type request_id: str
    :param model: Modelo que respondió
    :type model: str
    :param route: Motivo del enrutador para elegir ese modelo
    :type route: str
    :param cached_calls: Llamadas servidas desde la caché del gateway
    :type cached_calls: int
    :param cost_usd: Costo de la respuesta en USD
    :type cost_usd: float
    :param pii_masked: Tipos de PII enmascarados en la respuesta (vacía si no
        hubo)
    :type pii_masked: list[str]
    """

    answer: str
    steps: int
    tools_used: list[str]
    input_tokens: int
    output_tokens: int
    request_id: str
    model: str
    route: str
    cached_calls: int
    cost_usd: float
    pii_masked: list[str] = Field(default_factory=list)


def build_ask_request(max_question_chars: int) -> type[BaseModel]:
    """Crea el modelo de entrada de ``POST /ask`` con el largo máximo configurado.

    :param max_question_chars: Largo máximo de la pregunta
    :type max_question_chars: int
    :return: Clase Pydantic que valida la petición
    :rtype: type[pydantic.BaseModel]
    """

    class AskRequest(BaseModel):
        """Cuerpo de ``POST /ask``."""

        question: str = Field(min_length=1, max_length=max_question_chars)
        history: list[HistoryMessage] = Field(default_factory=list)

        @field_validator("question")
        @classmethod
        def question_not_blank(cls, value: str) -> str:
            """Rechaza preguntas que solo tienen espacios.

            :param value: Pregunta recibida
            :type value: str
            :return: Pregunta sin espacios al inicio ni al final
            :rtype: str
            :raises ValueError: Si la pregunta queda vacía
            """
            stripped = value.strip()
            if not stripped:
                raise ValueError("question must not be blank")
            return stripped

    return AskRequest


class AskService:
    """Responde preguntas con el agente y deja sus eventos y métricas.

    No guarda nada entre peticiones salvo los contadores de ``Metrics``.

    :param agent: Agente que responde
    :type agent: Agent
    :param events: Log de eventos JSON
    :type events: EventLogger
    :param metrics: Métricas del proceso
    :type metrics: Metrics
    :param tracer: Tracer de LangSmith o ``NoopTracer``
    :type tracer: Tracer
    :param costs: Configuración, modelos por nombre y precios
    :type costs: CostControls
    """

    # Cada colaborador es inyectable para las pruebas.
    def __init__(  # pylint: disable=too-many-arguments
        self,
        agent: Agent,
        events: EventLogger,
        metrics: Metrics,
        tracer: Tracer,
        *,
        costs: CostControls,
    ) -> None:
        self._agent = agent
        self._events = events
        self._metrics = metrics
        self._tracer = tracer
        self._costs = costs

    def answer(
        self,
        question: str,
        history: list[HistoryMessage],
        request_id: str,
        *,
        client: str | None = None,
    ) -> AskResponse:
        """Corre el agente y escribe los eventos ``audit`` y ``agent_run``.

        Recorta el historial a ``HISTORY_WINDOW`` mensajes, elige el modelo con
        el enrutador y calcula el costo con los tokens facturables. El evento
        ``agent_run`` solo lleva conteos: nunca la pregunta ni la respuesta.
        El nombre del cliente (nunca su clave) va a ``agent_run``, a cada
        ``audit`` y a los metadatos de la traza.

        Con ``PII_DETECTION=true`` revisa la pregunta y todo el historial (antes
        de recortarlo) y, si hay PII, no llama al modelo. La respuesta del
        modelo pasa por ``validate_output``: vacía, enmascarada y recortada.

        :param question: Pregunta ya validada
        :type question: str
        :param history: Mensajes previos de la conversación
        :type history: list[HistoryMessage]
        :param request_id: Id de la petición
        :type request_id: str
        :param client: Nombre del cliente autenticado
        :type client: str | None
        :return: Respuesta de ``POST /ask``
        :rtype: AskResponse
        :raises SensitiveDataError: Si la pregunta o el historial tienen PII
        :raises ModelUnavailableError: Si el modelo real no responde
        """
        settings = self._costs.settings
        if settings.pii_detection:
            self._block_sensitive_input(question, history, request_id, client)
        sent_history = window_history(history, settings.history_window)
        messages = [
            {"role": item.role, "content": item.content} for item in sent_history
        ]
        messages.append({"role": "user", "content": question})
        chosen = route(question, settings)

        def audit(tool: str, args: dict[str, Any]) -> None:
            """Registra una llamada a herramienta."""
            self._events.emit(
                "audit",
                request_id,
                action="tool_call",
                tool=tool,
                args=args,
                client=client,
            )

        run = self._tracer.wrap(
            self._agent.run,
            name="agent_run",
            run_type="chain",
            request_id=request_id,
            client=client,
        )
        result: AgentResult = run(
            messages,
            observer=audit,
            tracer=self._tracer,
            request_id=request_id,
            model=self._costs.models[chosen.model],
        )
        cost_usd = self._costs.prices.cost(
            chosen.model, result.billed_input_tokens, result.billed_output_tokens
        )
        guarded = validate_output(
            result.answer, settings.output_max_chars, settings.pii_detection
        )
        if guarded.masked_types:
            self._record_pii(PII_OUTPUT, guarded.masked_types, request_id, client)
        self._events.emit(
            "agent_run",
            request_id,
            question_chars=len(question),
            history_messages=len(history),
            history_sent=len(sent_history),
            steps=result.steps,
            tools=list(result.tools_used),
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            stopped=result.stopped,
            model=chosen.model,
            route=chosen.reason,
            cached_calls=result.cached_calls,
            cost_usd=cost_usd,
            client=client,
            pii_masked=list(guarded.masked_types),
        )
        self._metrics.add_tokens(result.input_tokens, result.output_tokens)
        self._metrics.add_cost(cost_usd)
        return AskResponse(
            answer=guarded.text,
            steps=result.steps,
            tools_used=list(result.tools_used),
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            request_id=request_id,
            model=chosen.model,
            route=chosen.reason,
            cached_calls=result.cached_calls,
            cost_usd=cost_usd,
            pii_masked=list(guarded.masked_types),
        )

    def _block_sensitive_input(
        self,
        question: str,
        history: Sequence[HistoryMessage],
        request_id: str,
        client: str | None,
    ) -> None:
        """Bloquea la petición si la pregunta o el historial tienen PII.

        Revisa todos los mensajes del historial, no solo los de la ventana.

        :param question: Pregunta ya validada
        :type question: str
        :param history: Mensajes previos de la conversación (completos)
        :type history: Sequence[HistoryMessage]
        :param request_id: Id de la petición
        :type request_id: str
        :param client: Nombre del cliente autenticado
        :type client: str | None
        :raises SensitiveDataError: Con los tipos encontrados (nunca los valores)
        """
        types = detect_all([question, *(item.content for item in history)])
        if types:
            self._record_pii(PII_INPUT, types, request_id, client)
            raise SensitiveDataError(types)

    def _record_pii(
        self,
        where: str,
        types: Sequence[str],
        request_id: str,
        client: str | None,
    ) -> None:
        """Audita una detección: evento, contador y tramo de traza.

        Solo registra los tipos; el valor detectado nunca llega aquí.

        :param where: ``input`` u ``output``
        :type where: str
        :param types: Tipos de PII detectados
        :type types: Sequence[str]
        :param request_id: Id de la petición
        :type request_id: str
        :param client: Nombre del cliente autenticado
        :type client: str | None
        """
        self._events.emit(
            "pii_detected",
            request_id,
            client=client,
            where=where,
            types=list(types),
        )
        if where == PII_INPUT:
            self._metrics.add_pii_blocked()
        else:
            self._metrics.add_pii_masked()
        span = self._tracer.wrap(
            report_pii_types,
            name=f"pii_{where}",
            run_type="chain",
            request_id=request_id,
            client=client,
            pii_types=types,
        )
        span(types)


def _register_routes(
    application: FastAPI,
    settings: Settings,
    service: AskService,
    metrics: Metrics,
    require_client: Callable[..., str],
) -> None:
    """Declara las rutas de la aplicación.

    ``POST /ask`` y ``GET /metrics`` dependen de ``require_client``; ``/`` y
    ``/health`` (y ``/docs``) quedan abiertos. La clave se revisa antes que el
    cuerpo: sin clave, una petición con cuerpo inválido da ``401``.

    :param application: Aplicación FastAPI
    :type application: fastapi.FastAPI
    :param settings: Configuración validada
    :type settings: Settings
    :param service: Servicio que responde las preguntas
    :type service: AskService
    :param metrics: Métricas del proceso
    :type metrics: Metrics
    :param require_client: Dependencia que exige clave y aplica el límite
    :type require_client: Callable[..., str]
    """
    ask_request = build_ask_request(settings.max_question_chars)
    client_dependency = Depends(require_client)

    @application.get("/", response_class=HTMLResponse)
    def home() -> HTMLResponse:
        """Sirve la página web."""
        return HTMLResponse(PAGE_PATH.read_text(encoding="utf-8"))

    @application.get("/health")
    def health() -> dict:
        """Informa que el proceso está vivo y su id."""
        return {"status": "ok", "pid": os.getpid()}

    @application.get("/metrics", dependencies=[client_dependency])
    def read_metrics() -> dict:
        """Devuelve las métricas, el costo acumulado y si se cumple el SLO."""
        return {
            **metrics.snapshot(settings.slo_p95_ms),
            "cost_usd": metrics.cost_usd(),
            **metrics.pii_counts(),
        }

    @application.post("/ask", response_model=AskResponse)
    def ask(
        client: Annotated[str, client_dependency],
        payload: ask_request,  # type: ignore[valid-type]
        http_request: Request,
    ) -> AskResponse:
        """Responde una pregunta con el agente, sin guardar nada."""
        return service.answer(
            payload.question,
            payload.history,
            http_request.state.request_id,
            client=client,
        )


def _register_model_unavailable(application: FastAPI, events: EventLogger) -> None:
    """Convierte ``ModelUnavailableError`` en ``502`` con su ``request_id``.

    El evento ``error`` lleva solo el tipo: nunca el mensaje, el token ni la
    respuesta del proveedor.

    :param application: Aplicación FastAPI
    :type application: fastapi.FastAPI
    :param events: Log de eventos JSON
    :type events: EventLogger
    """

    @application.exception_handler(ModelUnavailableError)
    async def model_unavailable(
        request: Request, error: ModelUnavailableError
    ) -> JSONResponse:
        """Responde ``502 {"detail": "model unavailable", "request_id"}``."""
        request_id = request.state.request_id
        events.emit("error", request_id, error_type=type(error).__name__)
        return JSONResponse(
            {"detail": MODEL_UNAVAILABLE_DETAIL, "request_id": request_id},
            status_code=MODEL_UNAVAILABLE_STATUS,
        )


def _register_sensitive_data(application: FastAPI) -> None:
    """Convierte ``SensitiveDataError`` en ``422`` con su ``request_id``.

    El ``detail`` solo lleva los tipos, nunca el dato. El evento
    ``pii_detected`` ya lo escribió el servicio.

    :param application: Aplicación FastAPI
    :type application: fastapi.FastAPI
    """

    @application.exception_handler(SensitiveDataError)
    async def sensitive_data(
        request: Request, error: SensitiveDataError
    ) -> JSONResponse:
        """Responde ``422`` con los tipos encontrados y el ``request_id``."""
        return JSONResponse(
            {"detail": error.detail, "request_id": request.state.request_id},
            status_code=SENSITIVE_DATA_STATUS,
        )


def _build_costs(
    settings: Settings,
    models: Mapping[str, LanguageModel],
    prices: PriceTable | None,
) -> CostControls:
    """Arma los controles de costo y verifica que todo modelo tenga precio.

    :param settings: Configuración validada
    :type settings: Settings
    :param models: Modelos por nombre
    :type models: Mapping[str, LanguageModel]
    :param prices: Tabla de precios; si falta, se lee de ``PRICES_PATH``
    :type prices: PriceTable | None
    :return: Configuración, modelos y precios listos
    :rtype: CostControls
    :raises ValueError: Si falta un modelo o un precio
    """
    names = (settings.model_small, settings.model_large)
    missing = [name for name in names if name not in models]
    if missing:
        raise ValueError(f"no model for: {', '.join(missing)}")
    prices = prices or PriceTable.from_file(settings.prices_path)
    prices.require(names)
    return CostControls(settings=settings, models=dict(models), prices=prices)


# Cada dependencia es inyectable para las pruebas; agruparlas no aclararía nada.
def create_app(  # pylint: disable=too-many-arguments
    settings: Settings | None = None,
    model: LanguageModel | None = None,
    directory: EmployeeDirectory | None = None,
    *,
    clock: Clock | None = None,
    log_stream: TextIO | None = None,
    metrics: Metrics | None = None,
    tracer: Tracer | None = None,
    models: Mapping[str, LanguageModel] | None = None,
    prices: PriceTable | None = None,
    rate_limiter: RateLimiter | None = None,
) -> FastAPI:
    """Construye la aplicación FastAPI con sus dependencias.

    Con ``ENVIRONMENT=production`` revisa las reglas de compliance antes de
    construir nada.

    :param settings: Configuración; si falta, se lee del entorno
    :type settings: Settings | None
    :param model: Un solo modelo para ambas rutas (como en la sesión 1)
    :type model: LanguageModel | None
    :param directory: Directorio de empleados; si falta, se lee del archivo
    :type directory: EmployeeDirectory | None
    :param clock: Reloj para la hora de los eventos y la latencia
    :type clock: Clock | None
    :param log_stream: Salida del log JSON; si falta, la salida estándar
    :type log_stream: TextIO | None
    :param metrics: Métricas del proceso; si faltan, se crean vacías
    :type metrics: Metrics | None
    :param tracer: Tracer; si falta, se crea según la configuración
    :type tracer: Tracer | None
    :param models: Modelos por nombre; si faltan (y no hay ``model``), se crean
        según la configuración
    :type models: Mapping[str, LanguageModel] | None
    :param prices: Tabla de precios; si falta, se lee de ``PRICES_PATH``
    :type prices: PriceTable | None
    :param rate_limiter: Límite por cliente; si falta, se crea con
        ``RATE_LIMIT_PER_MINUTE`` y el reloj inyectado
    :type rate_limiter: RateLimiter | None
    :return: Aplicación lista para servir
    :rtype: fastapi.FastAPI
    :raises ValueError: Si la configuración es inválida o un modelo no tiene
        precio
    :raises app.compliance.ComplianceError: Si la configuración de producción
        viola alguna regla (es un ``ValueError``)
    :raises FileNotFoundError: Si no existe el archivo de empleados o de precios
    """
    settings = settings or Settings.from_env(os.environ)
    enforce(settings)
    directory = directory or EmployeeDirectory.from_file(settings.employees_path)
    clock = clock or SystemClock()
    metrics = metrics if metrics is not None else Metrics()
    events = EventLogger(stream=log_stream, clock=clock, service=settings.service_name)
    if model is not None:
        models = {settings.model_small: model, settings.model_large: model}
    elif models is None:
        models = build_models(settings, directory.departments())
    costs = _build_costs(settings, models, prices)
    service = AskService(
        agent=Agent(
            model=costs.models[settings.model_small],
            directory=directory,
            max_steps=settings.agent_max_steps,
        ),
        events=events,
        metrics=metrics,
        tracer=tracer or build_tracer(settings),
        costs=costs,
    )
    rate_limiter = rate_limiter or RateLimiter(settings.rate_limit_per_minute, clock)
    application = FastAPI(title="HR Assistant")
    _register_routes(
        application,
        settings,
        service,
        metrics,
        build_require_client(ApiKeyAuth(settings.api_keys), rate_limiter),
    )
    _register_model_unavailable(application, events)
    _register_sensitive_data(application)
    application.add_middleware(
        ObservabilityMiddleware, events=events, metrics=metrics, clock=clock
    )
    return application


app = create_app()
