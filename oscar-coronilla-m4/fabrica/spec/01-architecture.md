# Sesión 1 · Arquitectura simple y lista para crecer

Producto: **HR Assistant**, un asistente de Recursos Humanos que responde preguntas sobre empleados.
El personal de RH lo usa desde una página web.

## Lo que debe hacer

1. Una API web (FastAPI) **sin estado**: no guarda nada entre peticiones. Escalar es correr más copias.
2. Un **solo agente** con dos herramientas de solo lectura sobre `data/employees.json`:
   - `get_employee(employee_id)`: un empleado por id, por ejemplo `EMP-0004`. Si no existe, lo dice.
   - `search_by_department(department)`: los empleados de un departamento.
3. El agente trabaja en un **bucle con tope**: en cada vuelta el modelo pide una herramienta o responde.
   Si llega al tope sin responder, contesta exactamente:
   `No pude completar la respuesta. Intenta con una pregunta más concreta.`
4. El modelo se usa a través de una **interfaz** (`complete(messages)`), para poder cambiarlo sin tocar el agente.
   En esta sesión solo existe el **modelo simulado**.
5. Una **página web** para el personal de RH.

## Protocolo entre el agente y el modelo

El modelo responde siempre un único objeto JSON:

- `{"tool": "<nombre>", "args": {...}}` para pedir una herramienta.
- `{"answer": "<respuesta en español>"}` para responder.

El agente agrega el resultado de la herramienta a la conversación como un mensaje `user` que empieza con
`Resultado de la herramienta: ` y vuelve a preguntar al modelo.

## Modelo simulado (`MODEL_PROVIDER=fake`)

Determinista, sin red ni costo. Decide con reglas sobre el último mensaje:

1. Si empieza con `Resultado de la herramienta: ` → `{"answer": "Según el directorio: <resultado>"}`.
2. Si contiene un id con forma `EMP-` y cuatro dígitos → pide `get_employee` con ese id.
3. Si menciona un departamento que existe en los datos → pide `search_by_department`.
4. Si no → `{"answer": "Pregúntame por un empleado (EMP-0001) o un departamento."}`.

Cuenta tokens de forma aproximada: tokens de entrada = palabras de todos los mensajes; de salida = palabras de su respuesta.

## API

| Método y ruta | Qué hace |
| --- | --- |
| `GET /` | La página web |
| `GET /health` | `{"status": "ok", "pid": <id del proceso>}` |
| `POST /ask` | Cuerpo `{"question": "...", "history": [{"role": "user" o "assistant", "content": "..."}]}`. `history` es opcional |

Respuesta de `POST /ask`: `{"answer", "steps", "tools_used", "input_tokens", "output_tokens"}`.

- `question` vacía o con más de `MAX_QUESTION_CHARS` caracteres → `422`.
- El historial lo manda el cliente. La API no lo guarda.

## Configuración (variables de entorno, con valores por omisión)

| Variable | Por omisión | Para qué |
| --- | --- | --- |
| `MODEL_PROVIDER` | `fake` | Qué modelo usar. En esta sesión solo `fake` |
| `AGENT_MAX_STEPS` | `3` | Tope de vueltas del bucle |
| `MAX_QUESTION_CHARS` | `2000` | Largo máximo de la pregunta |
| `EMPLOYEES_PATH` | `data/employees.json` | Los datos |

Un valor inválido (por ejemplo `AGENT_MAX_STEPS=0`) impide arrancar, con un mensaje claro.

## Página web (`app/static/index.html`)

- Un solo archivo HTML con CSS y JavaScript adentro, sin librerías ni compilación. Se sirve en `GET /`.
- Campo de pregunta `data-testid="question"`, botón `data-testid="send"`, y la conversación `data-testid="answer"`.
- Cada respuesta muestra el texto y las herramientas usadas.
- El navegador guarda el historial de la conversación y lo manda en `history`.
- El texto de las respuestas se pinta con `textContent`, **nunca** con `innerHTML`: así una respuesta no puede inyectar código.
- Si la API responde un error, se muestra un mensaje en español.

## Estructura del producto

```
product/
  app/      main.py (expone `app` y `create_app()`), agent.py, llm.py, directory.py, config.py, static/index.html
  data/     employees.json (copia de spec/employees.json)
  tests/    pruebas unitarias y escenarios Gherkin (los escribe qa-unit)
  doc/      architecture.md y adr/ (los escribe architect)
  requirements.txt
```

- `create_app()` recibe sus dependencias (configuración, modelo, directorio) para que las pruebas inyecten las suyas.
- Solo se usan las librerías de `requirements.txt` de la fábrica: fastapi, uvicorn, pydantic, httpx, pytest, pytest-bdd y pytest-cov.
- No lleva `pyproject.toml`.

## Reglas de QA.md que aplican desde ya

- Nombres de código, pruebas y mensajes de la API en inglés. Comentarios y docstrings en español, con docstrings estilo Sphinx (`:param:`, `:return:`) en clases y funciones públicas.
- Líneas de máximo 88 caracteres. Sin emojis.
- Sin `datetime.now()` directo: si hace falta la hora, se inyecta.
- Pruebas: escenarios Gherkin (pytest-bdd) para el comportamiento y pruebas unitarias para la lógica. Cobertura de 80 % o más.
- Decisiones de arquitectura en ADR (`doc/adr/NNNN-titulo.md`).

## Cómo se comprueba

- `uv run python -m verification unit`: las pruebas del producto pasan con cobertura de 80 % o más.
- `uv run python -m verification contract`: las pruebas de contrato de la fábrica pasan contra el producto corriendo.