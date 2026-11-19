"""Fixtures compartidas por las pruebas del HR Assistant.

Las pruebas nunca leen variables de entorno reales ni ``.env``: construyen
``Settings`` a mano y le inyectan a ``create_app()`` sus dependencias.
"""

import io
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.directory import EmployeeDirectory
from app.llm import ModelReply
from app.main import create_app
from app.metrics import Metrics
from app.security import parse_api_keys

# --- Sesion 4: un cliente de prueba con una clave de ejemplo -----------------
# La clave es de ejemplo, solo vive en las pruebas y tiene 16 o mas caracteres.
TEST_CLIENT = "tests"
TEST_API_KEY = "example-test-key-0001"
AUTH_HEADERS = {"X-API-Key": TEST_API_KEY}


def example_api_keys():
    """Devuelve las claves parseadas del cliente de prueba."""
    return parse_api_keys(f"{TEST_CLIENT}:{TEST_API_KEY}")


def authenticated_client(application):
    """Cliente HTTP de prueba que manda la clave del cliente de prueba."""
    return TestClient(application, raise_server_exceptions=False, headers=AUTH_HEADERS)


@pytest.fixture
def auth_headers():
    """Encabezados con la clave del cliente de prueba."""
    return dict(AUTH_HEADERS)


@pytest.fixture
def example_api_key():
    """Clave de ejemplo del cliente de prueba (para buscarla en el log)."""
    return TEST_API_KEY


EMPLOYEES = [
    {
        "id": "EMP-0001",
        "name": "Ana López",
        "department": "Tecnología",
        "role": "Analista de datos",
        "start_date": "2019-03-04",
        "status": "activo",
    },
    {
        "id": "EMP-0002",
        "name": "Luis Pérez",
        "department": "Ventas",
        "role": "Ejecutivo de cuenta",
        "start_date": "2021-07-19",
        "status": "activo",
    },
    {
        "id": "EMP-0003",
        "name": "Marta Ruiz",
        "department": "Tecnología",
        "role": "Desarrolladora",
        "start_date": "2016-11-02",
        "status": "baja",
    },
    {
        "id": "EMP-0004",
        "name": "Jorge Díaz",
        "department": "Tecnología",
        "role": "Líder técnico",
        "start_date": "2022-01-10",
        "status": "activo",
    },
    {
        "id": "EMP-0005",
        "name": "Sofía Gómez",
        "department": "Finanzas",
        "role": "Contadora",
        "start_date": "2020-05-25",
        "status": "activo",
    },
]


@pytest.fixture
def employees_file(tmp_path):
    """Escribe una copia de los datos de empleados en un archivo temporal."""
    path = tmp_path / "employees.json"
    path.write_text(json.dumps(EMPLOYEES, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def make_settings(employees_file):
    """Devuelve una fabrica de ``Settings`` validas con valores ajustables."""

    def _make(agent_max_steps=3, max_question_chars=2000):
        return Settings(
            model_provider="fake",
            agent_max_steps=agent_max_steps,
            max_question_chars=max_question_chars,
            employees_path=employees_file,
            api_keys=example_api_keys(),
        )

    return _make


@pytest.fixture
def directory(employees_file):
    """Directorio de empleados leido del archivo temporal."""
    return EmployeeDirectory.from_file(employees_file)


class ScriptedModel:
    """Modelo falso que devuelve respuestas guionizadas y anota lo que recibe.

    :param replies: Textos JSON que devuelve en orden; repite el ultimo al acabar
    :type replies: list[str]
    :param input_tokens: Tokens de entrada que informa en cada llamada
    :type input_tokens: int
    :param output_tokens: Tokens de salida que informa en cada llamada
    :type output_tokens: int
    """

    def __init__(self, replies, input_tokens=1, output_tokens=1):
        self.replies = list(replies)
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.calls = []

    def complete(self, messages):
        """Anota una copia de los mensajes y devuelve la siguiente respuesta."""
        self.calls.append([dict(message) for message in messages])
        index = min(len(self.calls), len(self.replies)) - 1
        return ModelReply(
            text=self.replies[index],
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
        )


@pytest.fixture
def scripted_model():
    """Fabrica de modelos guionizados para inyectar en el agente o la API."""
    return ScriptedModel


class FakeClock:
    """Reloj falso: la hora solo avanza cuando la prueba lo pide.

    Cumple la interfaz ``Clock`` de ``app.clock``: ``now_utc()`` y ``monotonic()``.
    """

    START = datetime(2026, 11, 7, 12, 30, 0, tzinfo=timezone.utc)

    def __init__(self):
        self.current = self.START
        self.seconds = 100.0

    def now_utc(self):
        """Devuelve la hora fija en UTC."""
        return self.current

    def monotonic(self):
        """Devuelve los segundos del reloj monotono falso."""
        return self.seconds

    def advance(self, seconds):
        """Avanza ambos relojes los segundos indicados."""
        self.seconds += seconds
        self.current += timedelta(seconds=seconds)


class SlowModel:
    """Modelo que tarda ``seconds`` en el reloj falso y luego delega.

    :param clock: Reloj falso que se adelanta en cada llamada
    :type clock: FakeClock
    :param inner: Modelo que da la respuesta real
    :param seconds: Segundos que tarda cada llamada
    :type seconds: float
    """

    def __init__(self, clock, inner, seconds):
        self.clock = clock
        self.inner = inner
        self.seconds = seconds

    def complete(self, messages):
        """Adelanta el reloj y devuelve la respuesta del modelo interno."""
        self.clock.advance(self.seconds)
        return self.inner.complete(messages)


class BrokenModel:
    """Modelo que siempre truena con un mensaje que no debe llegar al log."""

    MESSAGE = "secreto del proveedor: clave-xyz"

    def complete(self, messages):
        """Lanza ``RuntimeError`` sin importar los mensajes."""
        raise RuntimeError(self.MESSAGE)


class ObservedApp:
    """Aplicacion de prueba con su reloj, su log capturado y sus metricas.

    :param client: Cliente HTTP de prueba
    :param clock: Reloj falso inyectado
    :param stream: Salida del log en memoria
    :param metrics: Metricas del proceso inyectadas
    :param anonymous: Cliente HTTP de prueba que no manda clave
    """

    def __init__(  # pylint: disable=too-many-arguments
        self, client, clock, stream, metrics, anonymous=None
    ):
        self.client = client
        self.clock = clock
        self.stream = stream
        self.metrics = metrics
        self.anonymous = anonymous

    def log_text(self):
        """Devuelve todo lo escrito en el log."""
        return self.stream.getvalue()

    def events(self, name=None):
        """Lee cada linea del log como JSON; filtra por ``event`` si se pide."""
        lines = [line for line in self.log_text().splitlines() if line.strip()]
        parsed = [json.loads(line) for line in lines]
        if name is None:
            return parsed
        return [event for event in parsed if event["event"] == name]


@pytest.fixture
def fake_clock():
    """Reloj falso compartido por la aplicacion y los modelos de la prueba."""
    return FakeClock()


@pytest.fixture
def broken_model():
    """Modelo que siempre lanza ``RuntimeError``."""
    return BrokenModel()


@pytest.fixture
def make_slow_model(fake_clock, scripted_model):
    """Fabrica de modelos que tardan ``seconds`` y responden ``replies``."""

    def _make(replies, seconds):
        return SlowModel(fake_clock, scripted_model(replies, 5, 2), seconds)

    return _make


@pytest.fixture
def make_observed_app(make_settings, directory, fake_clock):
    """Fabrica de aplicaciones con reloj falso, log en memoria y metricas limpias."""

    def _make(model=None, settings=None):
        stream = io.StringIO()
        metrics = Metrics()
        application = create_app(
            settings=settings or make_settings(),
            model=model,
            directory=directory,
            clock=fake_clock,
            log_stream=stream,
            metrics=metrics,
        )
        anonymous = TestClient(application, raise_server_exceptions=False)
        return ObservedApp(
            authenticated_client(application), fake_clock, stream, metrics, anonymous
        )

    return _make


# --- Sesion 3: costos -------------------------------------------------------

SMALL_MODEL = "@cf/meta/llama-3.1-8b-instruct-fast"
LARGE_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
PRICES = {
    "currency": "USD",
    "unit": "per million tokens",
    "models": {
        "fake": {"input": 0.0, "output": 0.0},
        SMALL_MODEL: {"input": 0.045, "output": 0.384},
        LARGE_MODEL: {"input": 0.293, "output": 2.253},
    },
}
CF_VALUES = {
    "cf_account_id": "account-1",
    "cf_gateway_id": "gateway-1",
    "cf_api_token": "token-super-secreto",
}


@pytest.fixture
def prices_file(tmp_path):
    """Escribe una tabla de precios con los dos modelos en un archivo temporal."""
    path = tmp_path / "model_prices.json"
    path.write_text(json.dumps(PRICES), encoding="utf-8")
    return path


@pytest.fixture
def make_cost_settings(employees_file, prices_file):
    """Fabrica de ``Settings`` de la sesion 3 con cualquier campo ajustable."""

    def _make(**overrides):
        values = {
            "model_provider": "fake",
            "employees_path": employees_file,
            "prices_path": prices_file,
            "api_keys": example_api_keys(),
        }
        values.update(overrides)
        return Settings(**values)

    return _make


@pytest.fixture
def production_values():
    """Campos de una configuracion de produccion segura (gateway y clave larga)."""
    return {
        "environment": "production",
        "model_provider": "gateway",
        **CF_VALUES,
        "api_keys": parse_api_keys("web:" + "k" * 16),
    }


@pytest.fixture
def make_cost_app(make_cost_settings, directory, fake_clock):
    """Fabrica de aplicaciones con modelos por nombre, log en memoria y metricas.

    Sin ``models``, la aplicacion crea los modelos simulados con ``build_models``.
    """

    def _make(settings=None, models=None):
        stream = io.StringIO()
        metrics = Metrics()
        application = create_app(
            settings=settings or make_cost_settings(),
            directory=directory,
            models=models,
            clock=fake_clock,
            log_stream=stream,
            metrics=metrics,
        )
        anonymous = TestClient(application, raise_server_exceptions=False)
        return ObservedApp(
            authenticated_client(application), fake_clock, stream, metrics, anonymous
        )

    return _make
