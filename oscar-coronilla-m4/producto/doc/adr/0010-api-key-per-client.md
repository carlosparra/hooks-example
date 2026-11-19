# 0010. Una clave por cliente, revisada en una dependencia de FastAPI

Estado: propuesto

## Contexto

Al publicar el producto, cualquiera podría gastar el modelo o leer datos de empleados. Hace
falta saber quién pregunta, sin cuentas de usuario ni base de datos, y sin que la clave quede
nunca escrita en el log, en la traza ni en un error.

## Decisión

`API_KEYS` (`cliente:clave,...`) se lee y valida al arrancar en `security.py`; un error dice el
número de la entrada y su largo, nunca su texto. `POST /ask` y `GET /metrics` dependen de
`require_client` (`APIKeyHeader("X-API-Key", auto_error=False)`), que compara con
`hmac.compare_digest` contra todas las claves y responde
`401 {"detail": "invalid or missing API key"}`. El nombre del cliente va a `request.state`, a
los eventos `request`, `agent_run` y `audit`, y a los metadatos de la traza. `/`, `/health` y
`/docs` quedan abiertos.

## Consecuencias

- Se revoca o rota una clave cambiando `API_KEYS` en Render y reiniciando.
- La API sigue sin estado (ADR 0001): las claves son configuración.
- Con `API_KEYS` vacía en `development`, toda pregunta da 401; las pruebas inyectan su cliente.
- No hay roles: toda clave válida ve lo mismo.
