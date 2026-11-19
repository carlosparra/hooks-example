# Sesión 2 · Observabilidad: ¿qué pasó con la petición X?

Parte del producto de la sesión 1 (`spec/01-architecture.md`) y le agrega lo necesario para responder, con datos,
qué pasó con cualquier petición.

## Lo que debe hacer

1. **Un id por petición.** Si el cliente manda el encabezado `X-Request-ID`, se usa ese valor; si no, se genera
   un UUID. Toda respuesta lo devuelve en `X-Request-ID`, y `POST /ask` también en el cuerpo, como `request_id`.
2. **Log en JSON, una línea por evento**, en la salida estándar. Cada línea lleva `ts` (ISO 8601 en UTC),
   `service`, `event` y `request_id`. Eventos:
   - `request`: `method`, `path`, `status` y `latency_ms`, uno por cada petición.
   - `agent_run`: `question_chars`, `history_messages`, `steps`, `tools`, `input_tokens`, `output_tokens` y `stopped`.
     **Nunca** el texto de la pregunta ni de la respuesta.
   - `audit`: uno por cada herramienta que llama el agente, con `action: "tool_call"`, `tool` y `args`.
   - `error`: si algo truena, con el tipo de error (no el mensaje completo). La respuesta es `500` con
     `{"detail": "internal error", "request_id": ...}`.
3. **`GET /metrics`** de este proceso:
   `{"pid", "requests", "error_rate", "latency_ms": {"p50", "p95"}, "tokens": {"input", "output"},
   "slo": {"p95_ms_target", "met"}}`. `met` es `true` si el p95 está por debajo de `SLO_P95_MS`.
4. **Trazas en LangSmith (opcional).** Con `LANGSMITH_TRACING=true` y `LANGSMITH_API_KEY`, cada corrida del agente,
   cada llamada al modelo y cada herramienta quedan como trazas (`@traceable`), con el `request_id` en sus metadatos.
   Si `HIDE_INPUTS`/`HIDE_OUTPUTS` valen `true`, no se mandan entradas ni salidas. Sin la clave, el producto
   funciona igual y no intenta conectarse.
5. **La página web** muestra el `request_id` de cada respuesta, para que la persona lo pase a soporte.

## Configuración nueva

| Variable | Por omisión | Para qué |
| --- | --- | --- |
| `SERVICE_NAME` | `hr-assistant` | Campo `service` del log |
| `SLO_P95_MS` | `2000` | Meta de latencia p95 en milisegundos |
| `LANGSMITH_TRACING` | `false` | Enciende las trazas |
| `HIDE_INPUTS` / `HIDE_OUTPUTS` | `true` | No mandar a LangSmith el texto de preguntas ni respuestas (valor seguro por omisión) |

La clave `LANGSMITH_API_KEY` se lee del entorno y nunca se escribe en el log ni en el código.

## Reglas

- La hora se obtiene a través de un reloj inyectado (no `datetime.now()` directo), para que las pruebas sean
  deterministas.
- Se agrega `langsmith` a `requirements.txt`.
- El producto tiene `README.md` (qué es, cómo correrlo y sus variables) y `doc/` con la arquitectura y los ADR.
- Todo lo de la sesión 1 sigue funcionando.

## Cómo se comprueba

- `uv run python -m verification unit`: pruebas del producto, con cobertura de 80 % o más.
- `uv run python -m verification contract`: el contrato de las sesiones 1 y 2.
- `uv run python -m verification qa`: el estilo de QA.md (pylint, 88 columnas, sin emojis, documentos en su lugar).
- `qa-style` revisa lo que un script no ve y escribe `output/qa-review.md`, que empieza con `APROBADO` o `CAMBIOS`.
