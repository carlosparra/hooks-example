# HR Assistant

Asistente de Recursos Humanos que responde, desde una página web, preguntas sobre empleados
(por id, como `EMP-0004`, o por departamento). Es una API FastAPI sin estado con un agente de
bucle con tope que usa herramientas de solo lectura sobre `data/employees.json`.

Cada petición se puede rastrear y medir:

- **`request_id`**: se toma del encabezado `X-Request-ID` si es válido (1 a 128 caracteres de
  `[A-Za-z0-9._:-]`); si no, se genera un UUID. Toda respuesta lo devuelve en `X-Request-ID`,
  `POST /ask` también en el cuerpo, y la página lo muestra para pasarlo a soporte.
- **Log JSON** en la salida estándar, una línea por evento, con `ts` (UTC), `service`, `event`
  y `request_id`. Eventos: `request`, `agent_run` (solo conteos, nunca textos), `audit` (una
  por herramienta), `pii_detected` (solo los tipos) y `error` (solo el tipo de error).
- **`GET /metrics`**: peticiones, tasa de error, latencia p50/p95, tokens y si se cumple el SLO
  de este proceso.
- **Trazas en LangSmith** opcionales, con el `request_id` en los metadatos.

Cada respuesta también dice cuánto costó, y cuatro palancas la abaratan sin empeorarla:

- **Modelo real** con `MODEL_PROVIDER=gateway`: Cloudflare Workers AI a través de AI Gateway.
  Con `fake` hay dos modelos simulados que se llaman como `MODEL_SMALL` y `MODEL_LARGE`:
  responden igual, pero cada uno cuesta lo que su nombre en `data/model_prices.json`.
- **Enrutamiento**: una regla en código manda al modelo capaz las preguntas largas (más de
  `ROUTER_MAX_CHARS`) o con «compara», «resume», «explica», «por qué», «analiza» o «todos»;
  el resto va al modelo barato. Con `ROUTING=false` todo va al capaz.
- **Ventana de historial**: solo se mandan los últimos `HISTORY_WINDOW` mensajes.
- **Tope de salida**: `MODEL_MAX_TOKENS` en cada llamada.
- **Caché de AI Gateway**: con `CACHE_TTL_SECONDS` mayor que 0 se manda `cf-aig-cache-ttl`;
  una llamada con `cf-aig-cache-status: HIT` no cuesta.

Para publicarlo en internet de forma segura:

- **Una clave por cliente**: `API_KEYS` (`cliente:clave,cliente2:clave2`). `POST /ask` y
  `GET /metrics` exigen el encabezado `X-API-Key`; sin clave o con una inválida responden
  `401 {"detail": "invalid or missing API key"}`. El nombre del cliente va en el log
  (`client`), en la auditoría y en la traza; la clave nunca.
- **Límite por cliente**: más de `RATE_LIMIT_PER_MINUTE` peticiones en 60 segundos responden
  `429 {"detail": "rate limit exceeded"}` con `Retry-After` (segundos que faltan). El límite es
  por proceso y se vacía al reiniciar (ADR 0011).
- **Compliance como código**: con `ENVIRONMENT=production` el producto no arranca si usa el
  modelo `fake`, si `API_KEYS` está vacía o tiene una clave de menos de 16 caracteres, o si
  `LANGSMITH_TRACING=true` sin `HIDE_INPUTS` y `HIDE_OUTPUTS` en `true`, o si
  `PII_DETECTION` no vale `true`. La lista completa está
  en [`doc/compliance-checklist.md`](doc/compliance-checklist.md).
- **La página** pide la clave en un campo de contraseña; la guarda solo en `sessionStorage` (se
  borra al cerrar la pestaña) y la manda en `X-API-Key`. Con `401` muestra «Clave inválida» y
  con `429`, «Demasiadas preguntas; espera N segundos».

Para que los datos personales (PII) no lleguen al modelo ni salgan en una respuesta:

- **Detector local** (`app/pii.py`), con expresiones regulares y sin servicios externos:
  `email`, `phone` (México, 10 dígitos, con o sin `+52`), `curp`, `rfc`, `card` (13 a 19
  dígitos que pasan Luhn) y `clabe` (18 dígitos). Devuelve solo los tipos, nunca los valores;
  un número de empleado como `EMP-0004` no es PII.
- **Entrada**: si la pregunta o cualquier mensaje del historial (aunque quede fuera de la
  ventana) tiene PII, `POST /ask` responde `422 {"detail": "sensitive data detected: email,
  phone", "request_id": ...}` sin llamar al modelo y sin repetir el dato. La página muestra
  «Tu pregunta contiene datos sensibles; elimínalos y vuelve a intentar».
- **Salida**: la respuesta del modelo se valida: vacía, se cambia por el mensaje de tope de
  pasos; después cada dato se reemplaza por `[EMAIL]`, `[PHONE]`, `[CURP]`, `[RFC]`, `[CARD]`
  o `[CLABE]`, y al final se recorta a `OUTPUT_MAX_CHARS`. `pii_masked` lista los tipos.
- **Auditoría**: cada detección escribe `pii_detected` con `request_id`, `client`, `where`
  (`input` u `output`) y `types`, nunca el valor. `/metrics` cuenta `pii_blocked` y
  `pii_masked`, y la traza lleva `pii_types` en sus metadatos.
- Con `ENVIRONMENT=production` el producto no arranca si `PII_DETECTION` no vale `true`.

La arquitectura y las decisiones están en [`doc/architecture.md`](doc/architecture.md) y
[`doc/adr/`](doc/adr/).

## Cómo correrlo

Desde la carpeta `product/`:

```bash
pip install -r requirements.txt
uvicorn app.main:app --port 8000 --no-access-log
```

Abre `http://127.0.0.1:8000/`. `--no-access-log` evita que uvicorn mezcle líneas que no son
JSON con los eventos del producto. Sin `API_KEYS` toda pregunta responde `401`: define al menos
un cliente (en `.env` o en la terminal) y escribe su clave en el campo «Clave de acceso» de la
página.

Rutas:

| Ruta | Clave | Para qué |
| --- | --- | --- |
| `GET /` | No | Página web |
| `GET /health` | No | `{"status": "ok", "pid": ...}` |
| `GET /docs` | No | Documentación OpenAPI |
| `POST /ask` | Sí | `{question, history}` a `{answer, steps, tools_used, input_tokens, output_tokens, request_id, model, route, cached_calls, cost_usd, pii_masked}` |
| `GET /metrics` | Sí | Métricas del proceso, costo acumulado (`cost_usd`), `pii_blocked`, `pii_masked` y SLO |

La clave se revisa antes que el cuerpo: una petición sin clave da `401` aunque su cuerpo sea
inválido. Después de la clave se revisa el límite (`429`), luego el cuerpo (`422`) y, por
último, la PII (`422` con `sensitive data detected`). Una pregunta bloqueada por PII sí
consume cuota.

`route` es el motivo del enrutador: `routing_off`, `long_question`, `keyword` o
`short_question`. `cost_usd` está en USD y no se redondea.

Si el modelo real no responde (error de red, tiempo agotado, estado no 2xx o respuesta
ilegible), la respuesta es `502` con `{"detail": "model unavailable", "request_id": ...}`.
Si algo más falla dentro de la aplicación, la respuesta es `500` con
`{"detail": "internal error", "request_id": ...}`.

## Variables de entorno

Un valor inválido impide que la aplicación arranque. `.env.example` las lista todas, sin
valores secretos.

| Variable | Por omisión | Para qué |
| --- | --- | --- |
| `MODEL_PROVIDER` | `fake` | `fake` (simulado, sin red) o `gateway` (Cloudflare) |
| `AGENT_MAX_STEPS` | `3` | Tope de vueltas del bucle del agente |
| `MAX_QUESTION_CHARS` | `2000` | Largo máximo de la pregunta |
| `EMPLOYEES_PATH` | `data/employees.json` | Archivo de empleados (relativo a `product/`) |
| `SERVICE_NAME` | `hr-assistant` | Campo `service` del log |
| `SLO_P95_MS` | `2000` | Meta de latencia p95 en milisegundos |
| `LANGSMITH_TRACING` | `false` | Enciende las trazas (`true` o `false`) |
| `LANGSMITH_API_KEY` | (vacía) | Clave de LangSmith; sin ella no hay trazas |
| `HIDE_INPUTS` / `HIDE_OUTPUTS` | `true` | No mandar a LangSmith preguntas ni respuestas |
| `CF_ACCOUNT_ID` | (vacía) | Cuenta de Cloudflare |
| `CF_GATEWAY_ID` | `default` | Id del AI Gateway |
| `CF_API_TOKEN` | (vacía) | Token de Cloudflare (secreto) |
| `CF_AIG_TOKEN` | (vacía) | Token del gateway autenticado (secreto y opcional) |
| `MODEL_SMALL` | `@cf/meta/llama-3.1-8b-instruct-fast` | Modelo barato |
| `MODEL_LARGE` | `@cf/meta/llama-3.3-70b-instruct-fp8-fast` | Modelo capaz |
| `ROUTING` | `true` | Enrutamiento por pregunta (`true` o `false`) |
| `ROUTER_MAX_CHARS` | `80` | Preguntas más largas van al modelo capaz |
| `HISTORY_WINDOW` | `6` | Mensajes de historial que se mandan (0: ninguno) |
| `MODEL_MAX_TOKENS` | `300` | Tope de tokens de salida |
| `MODEL_TEMPERATURE` | `0` | Con 0 las evaluaciones son repetibles |
| `CACHE_TTL_SECONDS` | `0` | Caché del gateway en segundos (0: apagada) |
| `PRICES_PATH` | `data/model_prices.json` | Precios en USD por millón de tokens |
| `ENVIRONMENT` | `development` | Con `production` se aplican las reglas de compliance |
| `API_KEYS` | (vacía) | Clientes y claves, `cliente:clave,...` (secreto) |
| `RATE_LIMIT_PER_MINUTE` | `30` | Peticiones por cliente por minuto |
| `PII_DETECTION` | `true` | Bloquea la PII de entrada y enmascara la de salida (`true` o `false`); en producción debe ser `true` |
| `OUTPUT_MAX_CHARS` | `2000` | Largo máximo de una respuesta |

`ENVIRONMENT` solo acepta `development` o `production`, para que un valor mal escrito no se
salte las reglas. En `API_KEYS`, el nombre del cliente usa solo `[A-Za-z0-9._-]` (va al log) y
la clave, ASCII visible sin espacios; no se pueden repetir clientes ni claves. Si una entrada
está mal formada, el producto no arranca y el error dice su número y su largo, nunca su texto.
Para rotar o revocar una clave, cambia `API_KEYS` y reinicia.

Con `MODEL_PROVIDER=gateway`, faltar `CF_ACCOUNT_ID`, `CF_GATEWAY_ID` o `CF_API_TOKEN`
impide arrancar, igual que un `MODEL_SMALL` o `MODEL_LARGE` sin precio en `PRICES_PATH`.
La aplicación solo lee variables del entorno del proceso; no carga `.env` por sí sola.
Para usar el modelo real, desde `product/`:

1. Copia `.env.example` a `.env` (no se versiona), cambia `MODEL_PROVIDER` a `gateway` y llena
   `CF_ACCOUNT_ID`, `CF_GATEWAY_ID` y `CF_API_TOKEN`. Si tu gateway tiene autenticación,
   llena también `CF_AIG_TOKEN`: se manda en `cf-aig-authorization`; vacío, no se manda.
2. Arranca pidiéndole a uvicorn que cargue ese archivo (usa `python-dotenv`, que está en
   `requirements.txt`):

   ```bash
   uvicorn app.main:app --env-file .env --port 8000 --no-access-log
   ```

Otra opción es exportar las variables en la terminal antes de arrancar con el comando de
siempre, por ejemplo `export MODEL_PROVIDER=gateway` en bash o
`$env:MODEL_PROVIDER = "gateway"` en PowerShell (y lo mismo con las demás).

El token nunca aparece en el log, en los errores ni en `repr`. Revisa los precios de
`data/model_prices.json` antes de usarlos: cambian.

Las trazas solo se encienden con `LANGSMITH_TRACING=true` **y** una clave. Sin ellas no se
importa `langsmith` ni se abre ninguna conexión. La clave se lee del entorno: ponla en el
`.env` y arranca con `--env-file .env`, o expórtala en la terminal como arriba. Nunca se
escribe en el código ni en el log.

## Pruebas

Desde la raíz del repositorio:

```bash
uv run python -m verification unit      # pruebas del producto, cobertura >= 80 %
uv run python -m verification contract  # contrato HTTP de las sesiones 1 a 4 y del reto
uv run python -m verification qa        # pylint, 88 columnas, sin emojis, documentos
uv run python -m verification e2e       # pruebas de Playwright de la página
uv run python -m verification evaluate  # costo y calidad: línea base contra palancas
```

`e2e` necesita los navegadores de Playwright instalados una vez con
`playwright install chromium` (o `uv run playwright install chromium`).

Las pruebas inyectan un reloj falso, un log en memoria y modelos simulados; nunca usan la red.
El límite de peticiones usa el mismo reloj inyectado, así que se prueba sin esperar un minuto.
Las pruebas usan una clave de ejemplo que solo existe en ellas; `e2e` la recibe en
`E2E_API_KEY`.
El gateway se prueba con un cliente `httpx` inyectado (`MockTransport`). `evaluate` corre el
set de evaluación con el modelo simulado dos veces (línea base con `ROUTING=false` y sin
ventana, y la configuración por omisión) y pasa solo si la calidad no baja y el costo sí.

## Docker, CI y Render

### Imagen en local

El `Dockerfile` usa `python:3.12-slim`, instala `requirements.txt`, copia solo `app/` y
`data/` y corre como un usuario sin privilegios. uvicorn escucha en `PORT` (8000 si no se
define) con `--no-access-log`. Desde `product/`:

```bash
docker build --tag hr-assistant .
docker run --rm -p 8000:8000 -e PORT=8000 \
  -e API_KEYS="<cliente>:<clave-de-16-o-mas-caracteres>" hr-assistant
```

Cambia `<cliente>` y `<clave...>` por los tuyos; nunca escribas una clave real en un archivo
versionado. Sin más variables usa el modelo `fake` y `ENVIRONMENT=development`. Para el modelo
real, pasa las variables del `.env` con `docker run --env-file .env ...` en lugar de `-e`.

### Pipeline de CI

`.github/workflows/ci.yml` corre en cada `push` y `pull_request`, con solo permiso de lectura.
Tiene cuatro etapas encadenadas (cada una necesita que pase la anterior), y las que usan
Python instalan las dependencias solo con `pip install -r requirements.txt`:

1. **style**: `pylint` sobre `app` y `tests` con líneas de 88 columnas.
2. **unit**: `pytest` de `tests` con cobertura de `app` de al menos 80 %.
3. **e2e**: instala Chromium, arranca el producto con el modelo `fake` y una clave de prueba
   que solo existe en esa corrida, y corre las pruebas de Playwright de `e2e/`.
4. **docker**: construye la imagen con `docker build`.

### Publicación en Render

`render.yaml` es el Blueprint: un servicio web con `runtime: docker`, revisión de salud en
`/health` y `autoDeployTrigger: checksPass`, así que Render publica solo cuando los checks
de CI están en verde. Fija `ENVIRONMENT=production` (se aplican las reglas de compliance),
`MODEL_PROVIDER=gateway`, `HIDE_INPUTS` y `HIDE_OUTPUTS` en `true` y
`RATE_LIMIT_PER_MINUTE=30`.

Los secretos tienen `sync: false`: `API_KEYS`, `CF_ACCOUNT_ID`, `CF_API_TOKEN`,
`CF_AIG_TOKEN` y `CF_GATEWAY_ID`. Sus valores se escriben en Render > Environment (Render los
pide al crear el Blueprint), nunca en el repositorio. `LANGSMITH_API_KEY` es opcional y se
agrega ahí mismo solo si se encienden las trazas.

### Prueba de humo

Después de publicar, desde `product/`, con la clave de un cliente válido en el entorno (nunca
como argumento, para que no quede en el historial):

```bash
export SMOKE_API_KEY="<clave>"
python scripts/smoke.py https://<servicio>.onrender.com
```

En PowerShell: `$env:SMOKE_API_KEY = "<clave>"`. Comprueba que `GET /health` responde `200`,
`POST /ask` sin clave `401` y con clave `200`, e imprime `[OK]` o `[FAIL]` en cada una; la
clave nunca se imprime. Espera hasta 90 segundos por petición, porque el plan gratuito de
Render tarda en despertar. Códigos de salida:

| Código | Significado |
| --- | --- |
| `0` | Las tres comprobaciones pasan |
| `1` | Alguna comprobación falla |
| `2` | Falta la URL o `SMOKE_API_KEY` |
