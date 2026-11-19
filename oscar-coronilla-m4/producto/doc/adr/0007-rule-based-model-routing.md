# 0007. Enrutamiento por regla entre modelos con nombre

Estado: propuesto

## Contexto

La mayoría de las preguntas son búsquedas simples que un modelo chico resuelve igual que uno
grande, a una fracción del precio. Usar otro modelo para decidir costaría tokens y haría la
decisión difícil de probar. Las palancas se deben medir sin red.

## Decisión

`router.py` decide con una regla pura, una sola vez por pregunta: `MODEL_LARGE` si
`ROUTING=false`, si la pregunta pasa de `ROUTER_MAX_CHARS` o si contiene una palabra clave
(comparada sin acentos ni mayúsculas); si no, `MODEL_SMALL`. Devuelve el modelo y un motivo
(`routing_off`, `long_question`, `keyword`, `short_question`). `build_models` crea un modelo
por nombre (simulado o real) y `Agent.run` recibe el modelo de cada corrida, así el agente
sigue sin estado.

## Consecuencias

- La regla es determinista y se prueba sin red; el motivo queda en la respuesta y en el log.
- Un falso positivo solo encarece la pregunta; no la empeora.
- Con `fake`, los dos modelos responden igual y solo cambia el precio: `evaluate` mide costo.
- Cambiar la regla es cambiar código; no hay aprendizaje ni ajuste automático.
