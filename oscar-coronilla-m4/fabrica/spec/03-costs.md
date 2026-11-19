# Sesión 3 · Costos: abaratar cada respuesta sin empeorarla

Parte del producto de las sesiones 1 y 2. Agrega el modelo real (Cloudflare Workers AI a través de AI Gateway) y
cuatro palancas de costo. Cada palanca se mide: si baja la calidad, no se usa.

## Lo que debe hacer

1. **Modelo real** con `MODEL_PROVIDER=gateway`: llama a
   `https://gateway.ai.cloudflare.com/v1/{CF_ACCOUNT_ID}/{CF_GATEWAY_ID}/workers-ai/v1/chat/completions`
   con `Authorization: Bearer {CF_API_TOKEN}` y el cuerpo `{"model", "messages", "max_tokens", "temperature"}`.
   - Los tokens se leen de `usage.prompt_tokens` y `usage.completion_tokens`.
   - Si la llamada falla, la API responde `502 {"detail": "model unavailable", "request_id": ...}`.
   - Con `gateway`, faltar cualquiera de las tres variables `CF_*` impide arrancar.
   - Si `CF_AIG_TOKEN` tiene valor, también se manda el encabezado `cf-aig-authorization: Bearer {CF_AIG_TOKEN}`
   (gateways con autenticación). Si está vacío, no se manda.
2. **Palanca 1: enrutamiento.** Una regla en código (no otro modelo) elige el modelo por pregunta:
   - `MODEL_LARGE` si `ROUTING=false`, si la pregunta pasa de `ROUTER_MAX_CHARS` caracteres, o si contiene
     «compara», «resume», «explica», «por qué», «analiza» o «todos».
   - `MODEL_SMALL` en cualquier otro caso.
3. **Palanca 2: ventana de historial.** Al modelo solo se mandan los últimos `HISTORY_WINDOW` mensajes del historial.
4. **Palanca 3: tope de salida.** `MODEL_MAX_TOKENS` en cada llamada.
5. **Palanca 4: caché de AI Gateway.** Con `CACHE_TTL_SECONDS` mayor que 0 se manda el encabezado
   `cf-aig-cache-ttl`. Si el gateway responde `cf-aig-cache-status: HIT`, esa llamada cuenta como cacheada y no cuesta.
6. **Costo por respuesta.** Con los precios de `data/model_prices.json` (copia de `spec/model_prices.json`, en USD por
   millón de tokens). `POST /ask` agrega a su respuesta `model`, `route` (el motivo del enrutador), `cached_calls`
   y `cost_usd`. `/metrics` agrega `cost_usd` acumulado.
7. **El modelo simulado también tiene precio.** Con `MODEL_PROVIDER=fake` hay dos modelos simulados que se llaman como
   `MODEL_SMALL` y `MODEL_LARGE`. Responden igual, pero el costo se calcula con el precio de su nombre. Así las palancas
   se pueden medir sin red y sin gastar cuota.

## Configuración nueva

| Variable | Por omisión | Para qué |
| --- | --- | --- |
| `CF_ACCOUNT_ID`, `CF_GATEWAY_ID`, `CF_API_TOKEN` | vacías, `default`, vacía | Cuenta, gateway y token de Cloudflare (el token es secreto) |
| `CF_AIG_TOKEN` | vacía | Token del gateway autenticado (secreto y opcional) |
| `MODEL_SMALL` | `@cf/meta/llama-3.1-8b-instruct-fast` | Modelo barato |
| `MODEL_LARGE` | `@cf/meta/llama-3.3-70b-instruct-fp8-fast` | Modelo capaz |
| `ROUTING` | `true` | Enrutamiento por pregunta |
| `ROUTER_MAX_CHARS` | `80` | Preguntas más largas van al modelo capaz |
| `HISTORY_WINDOW` | `6` | Mensajes de historial que se mandan |
| `MODEL_MAX_TOKENS` | `300` | Tope de tokens de salida |
| `MODEL_TEMPERATURE` | `0` | Con 0 las evaluaciones son repetibles |
| `CACHE_TTL_SECONDS` | `0` | Caché del gateway (0: apagada) |
| `PRICES_PATH` | `data/model_prices.json` | Precios por modelo |

Se agrega `.env.example` con todas las variables del producto, sin valores secretos.

## Pruebas de punta a punta (las escribe `qa-e2e`)

En `product/e2e/`, con pytest-playwright y el producto corriendo con el modelo simulado:

- Escribir una pregunta, enviarla y ver la respuesta y su `request_id`.
- Una pregunta vacía muestra un mensaje de error en español.
- Una segunda pregunta mantiene la conversación anterior en pantalla.

## Cómo se comprueba

- `verification unit`, `contract` y `qa`, como en la sesión 2.
- `uv run python -m verification e2e`: las pruebas de Playwright pasan.
- `uv run python -m verification evaluate`: corre el set de evaluación dos veces con el modelo simulado.
  - **Línea base:** `ROUTING=false` y sin ventana.
  - **Con palancas:** la configuración por omisión.
  - Pasa solo si la calidad no baja y el costo sí baja.
