# 0006. Trazas opcionales en LangSmith detrás de un `Tracer` inyectado

Estado: propuesto

## Contexto

Ver cada corrida del agente, cada llamada al modelo y cada herramienta ayuda a depurar
errores, pero LangSmith es un servicio externo: manda datos fuera y necesita una clave. El
producto debe funcionar igual sin ella y las pruebas no deben usar red.

## Decisión

Un `Tracer` inyectado envuelve la corrida del agente (`chain`), `complete` del modelo (`llm`)
y cada herramienta (`tool`) con `@traceable`, con el `request_id` en los metadatos. Solo se
activa si `LANGSMITH_TRACING=true` y existe `LANGSMITH_API_KEY`; si no, se usa `NoopTracer`,
que devuelve las funciones sin cambios y no crea cliente. `HIDE_INPUTS` y `HIDE_OUTPUTS`
valen `true` por omisión. La clave la lee `langsmith` del entorno: no se guarda en `Settings`
ni se registra.

## Consecuencias

- Por omisión no sale ningún texto de preguntas ni respuestas a un tercero.
- El agente no importa `langsmith`: cambiar o quitar el proveedor de trazas no lo toca.
- Se agrega `langsmith` a `requirements.txt` aunque no se use sin clave.
- Las pruebas cubren el camino encendido con un `traceable` falso, no con el servicio real.
