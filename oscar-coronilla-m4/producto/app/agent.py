"""Agente con bucle con tope que usa herramientas de solo lectura."""

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

from app.directory import EmployeeDirectory
from app.llm import TOOL_RESULT_PREFIX, LanguageModel, ModelReply
from app.tracing import NoopTracer, Tracer

STEP_LIMIT_ANSWER = (
    "No pude completar la respuesta. Intenta con una pregunta más concreta."
)

ToolObserver = Callable[[str, dict[str, Any]], None]


class ToolError(Exception):
    """Error al interpretar o ejecutar un pedido del modelo."""


# Un campo por dato que la API reporta: agruparlos rompería la forma de la sesión 2.
@dataclass(frozen=True)
class AgentResult:  # pylint: disable=too-many-instance-attributes
    """Resultado de una ejecución del agente.

    :param answer: Respuesta final en español
    :type answer: str
    :param steps: Vueltas del bucle (llamadas al modelo)
    :type steps: int
    :param tools_used: Herramientas ejecutadas, en orden
    :type tools_used: list[str]
    :param input_tokens: Tokens de entrada sumados
    :type input_tokens: int
    :param output_tokens: Tokens de salida sumados
    :type output_tokens: int
    :param stopped: Verdadero si el bucle llegó al tope sin respuesta
    :type stopped: bool
    :param cached_calls: Llamadas al modelo servidas desde la caché
    :type cached_calls: int
    :param billed_input_tokens: Tokens de entrada sin las llamadas cacheadas
    :type billed_input_tokens: int
    :param billed_output_tokens: Tokens de salida sin las llamadas cacheadas
    :type billed_output_tokens: int
    """

    answer: str
    steps: int
    tools_used: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    stopped: bool = False
    cached_calls: int = 0
    billed_input_tokens: int = 0
    billed_output_tokens: int = 0


class _Usage:
    """Acumula tokens y llamadas cacheadas durante una corrida del agente."""

    def __init__(self) -> None:
        self.input_tokens = 0
        self.output_tokens = 0
        self.cached_calls = 0
        self.billed_input_tokens = 0
        self.billed_output_tokens = 0

    def add(self, reply: ModelReply) -> None:
        """Suma una respuesta del modelo; las cacheadas no se facturan.

        :param reply: Respuesta del modelo
        :type reply: ModelReply
        """
        self.input_tokens += reply.input_tokens
        self.output_tokens += reply.output_tokens
        if reply.cached:
            self.cached_calls += 1
            return
        self.billed_input_tokens += reply.input_tokens
        self.billed_output_tokens += reply.output_tokens

    def result(
        self, answer: str, steps: int, tools_used: list[str], stopped: bool = False
    ) -> AgentResult:
        """Arma el resultado de la corrida con los conteos acumulados.

        :param answer: Respuesta final
        :type answer: str
        :param steps: Vueltas del bucle
        :type steps: int
        :param tools_used: Herramientas ejecutadas
        :type tools_used: list[str]
        :param stopped: Si el bucle llegó al tope
        :type stopped: bool
        :return: Resultado del agente
        :rtype: AgentResult
        """
        return AgentResult(
            answer=answer,
            steps=steps,
            tools_used=tools_used,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            stopped=stopped,
            cached_calls=self.cached_calls,
            billed_input_tokens=self.billed_input_tokens,
            billed_output_tokens=self.billed_output_tokens,
        )


def _describe_employee(employee: Mapping[str, Any]) -> str:
    """Describe un empleado en una línea.

    :param employee: Registro del empleado
    :type employee: Mapping[str, Any]
    :return: Descripción legible
    :rtype: str
    """
    return (
        f"{employee.get('name')} ({employee.get('id')}), {employee.get('role')}, "
        f"departamento {employee.get('department')}, desde "
        f"{employee.get('start_date')}, estado {employee.get('status')}"
    )


class Agent:
    """Agente que alterna entre el modelo y las herramientas hasta responder.

    No guarda estado entre ejecuciones: cada ``run`` trabaja con su propia lista
    de mensajes.

    :param model: Modelo que cumple la interfaz ``complete(messages)``
    :type model: LanguageModel
    :param directory: Directorio de empleados de solo lectura
    :type directory: EmployeeDirectory
    :param max_steps: Tope de vueltas del bucle
    :type max_steps: int
    """

    def __init__(
        self, model: LanguageModel, directory: EmployeeDirectory, max_steps: int
    ) -> None:
        self._model = model
        self._directory = directory
        self._max_steps = max_steps
        self._tools: dict[str, Callable[..., str]] = {
            "get_employee": self._get_employee,
            "search_by_department": self._search_by_department,
        }

    # El modelo por corrida se agrega sin romper la firma de las sesiones previas.
    def run(  # pylint: disable=too-many-arguments
        self,
        messages: Sequence[Mapping[str, str]],
        observer: ToolObserver | None = None,
        tracer: Tracer | None = None,
        request_id: str = "",
        *,
        model: LanguageModel | None = None,
    ) -> AgentResult:
        """Ejecuta el bucle hasta obtener respuesta o alcanzar el tope.

        :param messages: Conversación inicial (historial y pregunta)
        :type messages: Sequence[Mapping[str, str]]
        :param observer: Función que recibe ``(tool, args)`` por cada herramienta
            ejecutada; sirve para el evento ``audit``
        :type observer: Callable[[str, dict], None] | None
        :param tracer: Tracer para las llamadas al modelo y a las herramientas
        :type tracer: Tracer | None
        :param request_id: Id de la petición, para los metadatos de las trazas
        :type request_id: str
        :param model: Modelo para esta corrida; si falta, el del constructor
        :type model: LanguageModel | None
        :return: Respuesta, pasos, herramientas, tokens y si llegó al tope
        :rtype: AgentResult
        """
        tracer = tracer or NoopTracer()
        complete = tracer.wrap(
            (model if model is not None else self._model).complete,
            name="llm",
            run_type="llm",
            request_id=request_id,
        )
        tools = {
            name: tracer.wrap(tool, name=name, run_type="tool", request_id=request_id)
            for name, tool in self._tools.items()
        }
        conversation = [dict(message) for message in messages]
        tools_used: list[str] = []
        usage = _Usage()
        for step in range(1, self._max_steps + 1):
            reply = complete(conversation)
            usage.add(reply)
            answer, result = self._act(reply.text, tools, tools_used, observer)
            if answer is not None:
                return usage.result(answer, step, tools_used)
            conversation.append({"role": "assistant", "content": reply.text})
            conversation.append(
                {"role": "user", "content": f"{TOOL_RESULT_PREFIX}{result}"}
            )
        return usage.result(STEP_LIMIT_ANSWER, self._max_steps, tools_used, True)

    @classmethod
    def _act(
        cls,
        text: str,
        tools: Mapping[str, Callable[..., str]],
        tools_used: list[str],
        observer: ToolObserver | None,
    ) -> tuple[str | None, str]:
        """Atiende una respuesta del modelo: la acepta o ejecuta la herramienta.

        :param text: Texto devuelto por el modelo
        :type text: str
        :param tools: Herramientas disponibles por nombre
        :type tools: Mapping[str, Callable[..., str]]
        :param tools_used: Lista de herramientas usadas; se le agrega la ejecutada
        :type tools_used: list[str]
        :param observer: Función que recibe ``(tool, args)`` o ``None``
        :type observer: Callable[[str, dict], None] | None
        :return: ``(respuesta, "")`` si el modelo respondió; si no,
            ``(None, resultado de la herramienta o del error)``
        :rtype: tuple[str | None, str]
        """
        try:
            request = cls._parse(text)
            if "answer" in request:
                return str(request["answer"]), ""
            result = cls._execute(request, tools)
        except ToolError as error:
            return None, f"Error: {error}"
        tools_used.append(request["tool"])
        if observer is not None:
            observer(request["tool"], dict(request.get("args", {})))
        return None, result

    @staticmethod
    def _parse(text: str) -> dict[str, Any]:
        """Interpreta el texto del modelo como un objeto JSON del protocolo.

        :param text: Texto devuelto por el modelo
        :type text: str
        :return: Objeto con ``answer`` o con ``tool`` y ``args``
        :rtype: dict[str, Any]
        :raises ToolError: Si el texto no cumple el protocolo
        """
        try:
            request = json.loads(text)
        except (TypeError, ValueError) as error:
            raise ToolError("la respuesta del modelo no es JSON válido") from error
        if not isinstance(request, dict):
            raise ToolError("la respuesta del modelo no es un objeto JSON")
        if "answer" in request:
            return request
        if not isinstance(request.get("tool"), str):
            raise ToolError("la respuesta no tiene 'answer' ni 'tool'")
        if not isinstance(request.get("args", {}), dict):
            raise ToolError("'args' debe ser un objeto JSON")
        return request

    @staticmethod
    def _execute(
        request: Mapping[str, Any], tools: Mapping[str, Callable[..., str]]
    ) -> str:
        """Ejecuta la herramienta pedida.

        :param request: Pedido con ``tool`` y ``args``
        :type request: Mapping[str, Any]
        :param tools: Herramientas disponibles por nombre (quizá con trazas)
        :type tools: Mapping[str, Callable[..., str]]
        :return: Resultado de la herramienta en texto
        :rtype: str
        :raises ToolError: Si la herramienta no existe o los argumentos fallan
        """
        name = request["tool"]
        tool = tools.get(name)
        if tool is None:
            raise ToolError(f"la herramienta '{name}' no existe")
        try:
            return tool(**request.get("args", {}))
        except TypeError as error:
            raise ToolError(f"argumentos inválidos para '{name}'") from error

    def _get_employee(self, employee_id: str) -> str:
        """Herramienta ``get_employee``.

        :param employee_id: Id del empleado
        :type employee_id: str
        :return: Descripción del empleado o aviso de que no existe
        :rtype: str
        """
        employee = self._directory.get_employee(employee_id)
        if employee is None:
            return f"El empleado {employee_id} no existe."
        return f"{_describe_employee(employee)}."

    def _search_by_department(self, department: str) -> str:
        """Herramienta ``search_by_department``.

        :param department: Nombre del departamento
        :type department: str
        :return: Lista de empleados o aviso de que no hay ninguno
        :rtype: str
        """
        employees = self._directory.search_by_department(department)
        if not employees:
            return f"No hay empleados en el departamento {department}."
        listing = "; ".join(_describe_employee(employee) for employee in employees)
        return f"Empleados de {department}: {listing}."
