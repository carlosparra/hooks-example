# 0008. Modelo real vía Cloudflare AI Gateway con cliente HTTP inyectado

Estado: propuesto

## Contexto

El producto necesita un modelo real (Workers AI) sin perder pruebas deterministas ni
arriesgar el token. El gateway además ofrece caché, que ahorra llamadas repetidas.

## Decisión

`gateway.py` implementa `LanguageModel` (ADR 0002) con un `httpx.Client` inyectado. Manda
`model`, `messages` con un prompt de sistema corto del protocolo JSON, `max_tokens` y
`temperature`; con `CACHE_TTL_SECONDS > 0` agrega `cf-aig-cache-ttl`. Lee `usage` y marca la
llamada como cacheada si `cf-aig-cache-status` es `HIT`. Cualquier fallo se convierte en
`ModelUnavailableError`, que la API responde como `502 {"detail": "model unavailable",
"request_id"}`. Con `gateway`, faltar una variable `CF_*` impide arrancar; el token se guarda
con `repr=False` y nunca se registra.

## Consecuencias

- Las pruebas usan `httpx.MockTransport`: sin red ni cuota.
- El agente no sabe de HTTP; cambiar de proveedor sigue siendo una clase nueva.
- No hay reintentos: un fallo se reporta en lugar de gastar más llamadas.
- La caché está apagada por omisión, porque las respuestas llevan datos de personas.
