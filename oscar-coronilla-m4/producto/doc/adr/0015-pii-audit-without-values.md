# 0015. Auditoría de PII sin valores

Estado: propuesto

## Contexto

Hay que saber cuántas veces se bloquea o enmascara PII y para qué cliente, pero el registro de
auditoría no puede convertirse en un segundo almacén de datos personales.

## Decisión

Cada detección escribe `pii_detected` con `request_id`, `client`, `where` (`input` u `output`)
y `types`; nunca el valor ni el texto. `Metrics` cuenta `pii_blocked` (peticiones bloqueadas) y
`pii_masked` (respuestas enmascaradas) fuera de `snapshot`; `/metrics` los agrega al nivel
superior. `Tracer.wrap` acepta `pii_types` para los metadatos y se registra un tramo
`pii_input` o `pii_output` cuya única entrada son los tipos.

## Consecuencias

- Se puede auditar y alertar sin exponer datos.
- Las pruebas buscan cada valor en todo el log y en las respuestas: no debe aparecer.
- Los contadores son por proceso, como el resto de métricas (ADR 0005).
