"""Configuración del HR Assistant leída de variables de entorno.

Un valor inválido lanza ``ValueError`` al construir ``Settings``, de modo que la
aplicación no arranca con una configuración rota.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from app.security import ApiKey, parse_api_keys

PRODUCT_DIR = Path(__file__).resolve().parent.parent
FAKE_PROVIDER = "fake"
GATEWAY_PROVIDER = "gateway"
SUPPORTED_PROVIDERS = (FAKE_PROVIDER, GATEWAY_PROVIDER)
DEFAULT_PROVIDER = FAKE_PROVIDER
DEFAULT_MAX_STEPS = 3
DEFAULT_MAX_QUESTION_CHARS = 2000
DEFAULT_EMPLOYEES_PATH = "data/employees.json"
DEFAULT_SERVICE_NAME = "hr-assistant"
DEFAULT_SLO_P95_MS = 2000
DEFAULT_GATEWAY_ID = "default"
DEFAULT_MODEL_SMALL = "@cf/meta/llama-3.1-8b-instruct-fast"
DEFAULT_MODEL_LARGE = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
DEFAULT_ROUTER_MAX_CHARS = 80
DEFAULT_HISTORY_WINDOW = 6
DEFAULT_MODEL_MAX_TOKENS = 300
DEFAULT_MODEL_TEMPERATURE = 0.0
DEFAULT_CACHE_TTL_SECONDS = 0
DEFAULT_PRICES_PATH = "data/model_prices.json"
DEVELOPMENT_ENVIRONMENT = "development"
PRODUCTION_ENVIRONMENT = "production"
SUPPORTED_ENVIRONMENTS = (DEVELOPMENT_ENVIRONMENT, PRODUCTION_ENVIRONMENT)
DEFAULT_RATE_LIMIT_PER_MINUTE = 30
DEFAULT_OUTPUT_MAX_CHARS = 2000
TRUE_VALUES = ("true",)
FALSE_VALUES = ("false",)


def _parse_positive_int(name: str, raw: str) -> int:
    """Convierte un texto en entero positivo o falla con un mensaje claro.

    :param name: Nombre de la variable de entorno, para el mensaje de error
    :type name: str
    :param raw: Valor leído del entorno
    :type raw: str
    :return: El valor como entero
    :rtype: int
    :raises ValueError: Si el valor no es un entero
    """
    try:
        return int(raw.strip())
    except ValueError as error:
        raise ValueError(
            f"{name} must be a positive integer, got {raw!r}"
        ) from error


def _parse_float(name: str, raw: str) -> float:
    """Convierte un texto en número decimal o falla con un mensaje claro.

    :param name: Nombre de la variable de entorno, para el mensaje de error
    :type name: str
    :param raw: Valor leído del entorno
    :type raw: str
    :return: El valor como número decimal
    :rtype: float
    :raises ValueError: Si el valor no es un número
    """
    try:
        return float(raw.strip())
    except ValueError as error:
        raise ValueError(f"{name} must be a number, got {raw!r}") from error


def _check_minimum(name: str, value: float, minimum: float) -> None:
    """Verifica que un valor numérico no sea menor que su mínimo.

    :param name: Nombre de la variable de entorno, para el mensaje de error
    :type name: str
    :param value: Valor a revisar
    :type value: float
    :param minimum: Valor mínimo permitido
    :type minimum: float
    :raises ValueError: Si el valor es menor que el mínimo
    """
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}, got {value!r}")


def _parse_bool(name: str, raw: str) -> bool:
    """Convierte ``true`` o ``false`` (sin distinguir mayúsculas) en booleano.

    :param name: Nombre de la variable de entorno, para el mensaje de error
    :type name: str
    :param raw: Valor leído del entorno
    :type raw: str
    :return: El valor como booleano
    :rtype: bool
    :raises ValueError: Si el valor no es ``true`` ni ``false``
    """
    value = raw.strip().lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    raise ValueError(f"{name} must be 'true' or 'false', got {raw!r}")


def _resolve_path(raw: str | Path) -> Path:
    """Resuelve una ruta relativa contra la carpeta ``product/``.

    :param raw: Ruta absoluta o relativa
    :type raw: str | pathlib.Path
    :return: Ruta absoluta
    :rtype: pathlib.Path
    """
    path = Path(raw)
    return path if path.is_absolute() else PRODUCT_DIR / path


# Una variable de entorno por atributo: agruparlas solo ocultaría la configuración.
@dataclass(frozen=True)
class Settings:  # pylint: disable=too-many-instance-attributes
    """Configuración inmutable de la aplicación.

    Nunca guarda el valor de ``LANGSMITH_API_KEY``: solo si está presente. El
    token y la cuenta de Cloudflare se guardan, pero no aparecen en ``repr``.

    :param model_provider: Proveedor de modelo: ``fake`` o ``gateway``
    :type model_provider: str
    :param agent_max_steps: Tope de vueltas del bucle del agente
    :type agent_max_steps: int
    :param max_question_chars: Largo máximo de la pregunta
    :type max_question_chars: int
    :param employees_path: Ruta del archivo JSON de empleados
    :type employees_path: str | pathlib.Path
    :param service_name: Campo ``service`` del log
    :type service_name: str
    :param slo_p95_ms: Meta de latencia p95 en milisegundos
    :type slo_p95_ms: int
    :param langsmith_tracing: Si se pidieron trazas en LangSmith
    :type langsmith_tracing: bool
    :param hide_inputs: No mandar a LangSmith las entradas
    :type hide_inputs: bool
    :param hide_outputs: No mandar a LangSmith las salidas
    :type hide_outputs: bool
    :param langsmith_key_present: Si ``LANGSMITH_API_KEY`` tiene valor
    :type langsmith_key_present: bool
    :param cf_account_id: Cuenta de Cloudflare (no aparece en ``repr``)
    :type cf_account_id: str
    :param cf_gateway_id: Id del AI Gateway
    :type cf_gateway_id: str
    :param cf_api_token: Token de Cloudflare; secreto, no aparece en ``repr``
    :type cf_api_token: str
    :param cf_aig_token: Token del gateway autenticado; secreto y opcional, no
        aparece en ``repr``
    :type cf_aig_token: str
    :param model_small: Nombre del modelo barato
    :type model_small: str
    :param model_large: Nombre del modelo capaz
    :type model_large: str
    :param routing: Si se elige el modelo por pregunta
    :type routing: bool
    :param router_max_chars: Preguntas más largas van al modelo capaz
    :type router_max_chars: int
    :param history_window: Mensajes de historial que se mandan al modelo
    :type history_window: int
    :param model_max_tokens: Tope de tokens de salida por llamada
    :type model_max_tokens: int
    :param model_temperature: Temperatura del modelo real
    :type model_temperature: float
    :param cache_ttl_seconds: Segundos de caché del gateway (0: apagada)
    :type cache_ttl_seconds: int
    :param prices_path: Ruta del archivo JSON de precios por modelo
    :type prices_path: str | pathlib.Path
    :param environment: ``development`` o ``production`` (aplica compliance)
    :type environment: str
    :param api_keys: Claves por cliente; secretas, no aparecen en ``repr``
    :type api_keys: tuple[ApiKey, ...]
    :param rate_limit_per_minute: Peticiones por cliente por minuto
    :type rate_limit_per_minute: int
    :param pii_detection: Si se bloquea la PII de entrada y se enmascara la de
        salida
    :type pii_detection: bool
    :param output_max_chars: Largo máximo de una respuesta
    :type output_max_chars: int
    :raises ValueError: Si algún valor es inválido
    """

    model_provider: str = DEFAULT_PROVIDER
    agent_max_steps: int = DEFAULT_MAX_STEPS
    max_question_chars: int = DEFAULT_MAX_QUESTION_CHARS
    employees_path: Path = PRODUCT_DIR / DEFAULT_EMPLOYEES_PATH
    service_name: str = DEFAULT_SERVICE_NAME
    slo_p95_ms: int = DEFAULT_SLO_P95_MS
    langsmith_tracing: bool = False
    hide_inputs: bool = True
    hide_outputs: bool = True
    langsmith_key_present: bool = False
    cf_account_id: str = field(default="", repr=False)
    cf_gateway_id: str = DEFAULT_GATEWAY_ID
    cf_api_token: str = field(default="", repr=False)
    cf_aig_token: str = field(default="", repr=False)
    model_small: str = DEFAULT_MODEL_SMALL
    model_large: str = DEFAULT_MODEL_LARGE
    routing: bool = True
    router_max_chars: int = DEFAULT_ROUTER_MAX_CHARS
    history_window: int = DEFAULT_HISTORY_WINDOW
    model_max_tokens: int = DEFAULT_MODEL_MAX_TOKENS
    model_temperature: float = DEFAULT_MODEL_TEMPERATURE
    cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS
    prices_path: Path = PRODUCT_DIR / DEFAULT_PRICES_PATH
    environment: str = DEVELOPMENT_ENVIRONMENT
    api_keys: tuple[ApiKey, ...] = field(default=(), repr=False)
    rate_limit_per_minute: int = DEFAULT_RATE_LIMIT_PER_MINUTE
    pii_detection: bool = True
    output_max_chars: int = DEFAULT_OUTPUT_MAX_CHARS

    @property
    def tracing_enabled(self) -> bool:
        """Indica si las trazas están encendidas: hace falta la bandera y la clave.

        :return: ``True`` solo con ``LANGSMITH_TRACING=true`` y clave presente
        :rtype: bool
        """
        return self.langsmith_tracing and self.langsmith_key_present

    def __post_init__(self) -> None:
        """Valida los valores y normaliza la ruta de datos."""
        if self.model_provider not in SUPPORTED_PROVIDERS:
            raise ValueError(
                f"MODEL_PROVIDER must be one of {SUPPORTED_PROVIDERS}, "
                f"got {self.model_provider!r}"
            )
        if self.agent_max_steps < 1:
            raise ValueError(
                "AGENT_MAX_STEPS must be a positive integer, "
                f"got {self.agent_max_steps!r}"
            )
        if self.max_question_chars < 1:
            raise ValueError(
                "MAX_QUESTION_CHARS must be a positive integer, "
                f"got {self.max_question_chars!r}"
            )
        if self.slo_p95_ms < 1:
            raise ValueError(
                f"SLO_P95_MS must be a positive integer, got {self.slo_p95_ms!r}"
            )
        if not self.service_name:
            raise ValueError("SERVICE_NAME must not be empty")
        self._validate_costs()
        self._validate_access()
        object.__setattr__(self, "employees_path", _resolve_path(self.employees_path))
        object.__setattr__(self, "prices_path", _resolve_path(self.prices_path))

    def _validate_costs(self) -> None:
        """Valida las variables de la sesión de costos.

        Con ``gateway``, las tres variables ``CF_*`` son obligatorias. El mensaje
        de error nombra la variable, nunca su valor.

        :raises ValueError: Si algún valor es inválido o falta uno obligatorio
        """
        for name, value, minimum in (
            ("ROUTER_MAX_CHARS", self.router_max_chars, 1),
            ("HISTORY_WINDOW", self.history_window, 0),
            ("MODEL_MAX_TOKENS", self.model_max_tokens, 1),
            ("MODEL_TEMPERATURE", self.model_temperature, 0),
            ("CACHE_TTL_SECONDS", self.cache_ttl_seconds, 0),
        ):
            _check_minimum(name, value, minimum)
        for name, value in (
            ("MODEL_SMALL", self.model_small),
            ("MODEL_LARGE", self.model_large),
        ):
            if not value:
                raise ValueError(f"{name} must not be empty")
        if self.model_provider != GATEWAY_PROVIDER:
            return
        for name, value in (
            ("CF_ACCOUNT_ID", self.cf_account_id),
            ("CF_GATEWAY_ID", self.cf_gateway_id),
            ("CF_API_TOKEN", self.cf_api_token),
        ):
            if not value:
                raise ValueError(f"{name} is required with MODEL_PROVIDER=gateway")

    def _validate_access(self) -> None:
        """Valida las variables de la sesión de producción y del reto de PII.

        Solo se aceptan dos entornos, para que un valor mal escrito (``prod``)
        no se salte las reglas de compliance. Nunca muestra las claves.

        :raises ValueError: Si el entorno, el límite, la detección de PII o el
            largo máximo de la respuesta son inválidos
        """
        if self.environment not in SUPPORTED_ENVIRONMENTS:
            raise ValueError(
                f"ENVIRONMENT must be one of {SUPPORTED_ENVIRONMENTS}, "
                f"got {self.environment!r}"
            )
        _check_minimum("RATE_LIMIT_PER_MINUTE", self.rate_limit_per_minute, 1)
        _check_minimum("OUTPUT_MAX_CHARS", self.output_max_chars, 1)
        if not isinstance(self.pii_detection, bool):
            raise ValueError("PII_DETECTION must be 'true' or 'false'")
        object.__setattr__(self, "api_keys", tuple(self.api_keys))

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> "Settings":
        """Construye la configuración a partir de un mapa de variables de entorno.

        :param environ: Variables de entorno (por ejemplo ``os.environ``)
        :type environ: Mapping[str, str]
        :return: Configuración validada
        :rtype: Settings
        :raises ValueError: Si algún valor es inválido
        """
        return cls(
            model_provider=environ.get("MODEL_PROVIDER", DEFAULT_PROVIDER).strip(),
            agent_max_steps=_parse_positive_int(
                "AGENT_MAX_STEPS",
                environ.get("AGENT_MAX_STEPS", str(DEFAULT_MAX_STEPS)),
            ),
            max_question_chars=_parse_positive_int(
                "MAX_QUESTION_CHARS",
                environ.get("MAX_QUESTION_CHARS", str(DEFAULT_MAX_QUESTION_CHARS)),
            ),
            employees_path=environ.get("EMPLOYEES_PATH", DEFAULT_EMPLOYEES_PATH),
            service_name=environ.get("SERVICE_NAME", DEFAULT_SERVICE_NAME).strip(),
            slo_p95_ms=_parse_positive_int(
                "SLO_P95_MS", environ.get("SLO_P95_MS", str(DEFAULT_SLO_P95_MS))
            ),
            langsmith_tracing=_parse_bool(
                "LANGSMITH_TRACING", environ.get("LANGSMITH_TRACING", "false")
            ),
            hide_inputs=_parse_bool("HIDE_INPUTS", environ.get("HIDE_INPUTS", "true")),
            hide_outputs=_parse_bool(
                "HIDE_OUTPUTS", environ.get("HIDE_OUTPUTS", "true")
            ),
            langsmith_key_present=bool(
                environ.get("LANGSMITH_API_KEY", "").strip()
            ),
            **_cost_values(environ),
            **_access_values(environ),
            **_pii_values(environ),
        )


def _pii_values(environ: Mapping[str, str]) -> dict[str, object]:
    """Lee del entorno las variables del reto de PII.

    :param environ: Variables de entorno (por ejemplo ``os.environ``)
    :type environ: Mapping[str, str]
    :return: Argumentos de ``Settings`` para la detección y el largo máximo
    :rtype: dict[str, object]
    :raises ValueError: Si algún valor no se puede convertir
    """
    return {
        "pii_detection": _parse_bool(
            "PII_DETECTION", environ.get("PII_DETECTION", "true")
        ),
        "output_max_chars": _parse_positive_int(
            "OUTPUT_MAX_CHARS",
            environ.get("OUTPUT_MAX_CHARS", str(DEFAULT_OUTPUT_MAX_CHARS)),
        ),
    }


def _access_values(environ: Mapping[str, str]) -> dict[str, object]:
    """Lee del entorno las variables de la sesión de producción.

    El error de ``API_KEYS`` dice el número de la entrada y su largo, nunca su
    texto.

    :param environ: Variables de entorno (por ejemplo ``os.environ``)
    :type environ: Mapping[str, str]
    :return: Argumentos de ``Settings`` para el entorno, las claves y el límite
    :rtype: dict[str, object]
    :raises ValueError: Si algún valor no se puede convertir
    """
    return {
        "environment": environ.get("ENVIRONMENT", DEVELOPMENT_ENVIRONMENT)
        .strip()
        .lower(),
        "api_keys": parse_api_keys(environ.get("API_KEYS", "")),
        "rate_limit_per_minute": _parse_positive_int(
            "RATE_LIMIT_PER_MINUTE",
            environ.get(
                "RATE_LIMIT_PER_MINUTE", str(DEFAULT_RATE_LIMIT_PER_MINUTE)
            ),
        ),
    }


def _cost_values(environ: Mapping[str, str]) -> dict[str, object]:
    """Lee del entorno las variables de la sesión de costos.

    :param environ: Variables de entorno (por ejemplo ``os.environ``)
    :type environ: Mapping[str, str]
    :return: Argumentos de ``Settings`` para el modelo real y las palancas
    :rtype: dict[str, object]
    :raises ValueError: Si algún valor no se puede convertir
    """
    return {
        "cf_account_id": environ.get("CF_ACCOUNT_ID", "").strip(),
        "cf_gateway_id": environ.get("CF_GATEWAY_ID", DEFAULT_GATEWAY_ID).strip(),
        "cf_api_token": environ.get("CF_API_TOKEN", "").strip(),
        "cf_aig_token": environ.get("CF_AIG_TOKEN", "").strip(),
        "model_small": environ.get("MODEL_SMALL", DEFAULT_MODEL_SMALL).strip(),
        "model_large": environ.get("MODEL_LARGE", DEFAULT_MODEL_LARGE).strip(),
        "routing": _parse_bool("ROUTING", environ.get("ROUTING", "true")),
        "router_max_chars": _parse_positive_int(
            "ROUTER_MAX_CHARS",
            environ.get("ROUTER_MAX_CHARS", str(DEFAULT_ROUTER_MAX_CHARS)),
        ),
        "history_window": _parse_positive_int(
            "HISTORY_WINDOW",
            environ.get("HISTORY_WINDOW", str(DEFAULT_HISTORY_WINDOW)),
        ),
        "model_max_tokens": _parse_positive_int(
            "MODEL_MAX_TOKENS",
            environ.get("MODEL_MAX_TOKENS", str(DEFAULT_MODEL_MAX_TOKENS)),
        ),
        "model_temperature": _parse_float(
            "MODEL_TEMPERATURE",
            environ.get("MODEL_TEMPERATURE", str(DEFAULT_MODEL_TEMPERATURE)),
        ),
        "cache_ttl_seconds": _parse_positive_int(
            "CACHE_TTL_SECONDS",
            environ.get("CACHE_TTL_SECONDS", str(DEFAULT_CACHE_TTL_SECONDS)),
        ),
        "prices_path": environ.get("PRICES_PATH", DEFAULT_PRICES_PATH),
    }
