# Sesión 4 · Producción: publicarlo de forma segura

Parte del producto de las sesiones 1 a 3. Lo cierra con acceso por clave, límite de peticiones y reglas de compliance
que se revisan solas. Lo empaqueta en un contenedor, con un pipeline de CI que los ingenieros pueden ver, y lo
publica en Render solo si el pipeline pasa.

## Lo que debe hacer

1. **Una clave por cliente.**
   - `API_KEYS` tiene la forma `cliente:clave,cliente2:clave2`.
   - `POST /ask` y `GET /metrics` exigen el encabezado `X-API-Key`. Sin clave o con una inválida, responden
     `401 {"detail": "invalid or missing API key"}`.
   - `GET /`, `GET /health` y `/docs` no piden clave.
   - El nombre del cliente va en el log (`client`), en la auditoría y en los metadatos de la traza.
   - **La clave nunca se escribe** en el log, en la traza ni en un mensaje de error.
   - Si `API_KEYS` está mal formada, el producto no arranca. El error dice qué entrada falla y su largo, nunca su valor.
2. **Límite de peticiones por cliente.** Más de `RATE_LIMIT_PER_MINUTE` peticiones en un minuto →
   `429 {"detail": "rate limit exceeded"}` con el encabezado `Retry-After` (segundos que faltan). El reloj se inyecta.
3. **Compliance como código.** Con `ENVIRONMENT=production`, el producto **se niega a arrancar** si:
   - `MODEL_PROVIDER` es `fake`.
   - `API_KEYS` está vacía o alguna clave tiene menos de 16 caracteres.
   - Las trazas están encendidas y `HIDE_INPUTS` o `HIDE_OUTPUTS` no valen `true`.

   `doc/compliance-checklist.md` tiene una tabla con tres columnas: la regla, dónde está en el código y cómo se
   comprueba.
4. **La página web** tiene un campo de clave (`data-testid="api-key"`, tipo contraseña).
   - La clave se guarda en `sessionStorage`, nunca en `localStorage` ni en el código de la página, y se manda en
     `X-API-Key`.
   - Con `401` muestra «Clave inválida». Con `429`, «Demasiadas preguntas; espera N segundos».
5. **Contenedor.**
   - `Dockerfile` con `python:3.12-slim`, un usuario que no es root y
     `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`.
   - `.dockerignore` que deja fuera `.env`, `tests/`, `e2e/` y los cachés.
6. **Pipeline de CI** en `.github/workflows/ci.yml`. Corre en cada push y en cada pull request, con cuatro trabajos
   encadenados (`needs`), para que los ingenieros vean cada etapa en la pestaña Actions:
   1. `style`: pylint con las **mismas opciones** que `verification/qa.py` (88 columnas y los mismos avisos
      desactivados), para que el CI y la verificación local midan lo mismo.
   2. `unit`: pruebas y BDD con cobertura de 80 % o más.
   3. `e2e`: Playwright con el modelo simulado.
   4. `docker`: `docker build` de la imagen.
7. **Render.** `render.yaml` es un Blueprint con un servicio web:
   - El servicio se llama **igual que el repositorio** que da la persona. Así no choca con un servicio que ya exista
     en su cuenta de Render, porque Render actualizaría ese en lugar de crear uno nuevo.
   - `runtime: docker`, `plan: free`, `healthCheckPath: /health`.
   - `autoDeployTrigger: checksPass`: Render publica solo si el pipeline pasa.
   - `ENVIRONMENT=production`, `MODEL_PROVIDER=gateway`, `HIDE_INPUTS=true` y `HIDE_OUTPUTS=true`.
   - Los secretos (`API_KEYS`, `CF_ACCOUNT_ID`, `CF_API_TOKEN`, `CF_AIG_TOKEN` y `CF_GATEWAY_ID`) con `sync: false`: se
     escriben en Render y nunca en el repositorio. Render exige un valor para cada uno al crear el Blueprint, por eso
     `LANGSMITH_API_KEY`, que es opcional, no va ahí: se agrega en Render > Environment si se encienden las trazas.
8. **Prueba de humo** en `scripts/smoke.py <url>`. Lee la clave de la variable `SMOKE_API_KEY`, nunca de un
   argumento, y comprueba tres cosas, imprimiendo `[OK]` o `[FAIL]` en cada una:
   - `/health` responde `200`.
   - `/ask` sin clave responde `401`.
   - `/ask` con clave responde `200`.

## Pruebas de punta a punta (las actualiza `qa-e2e`)

- Las pruebas de la sesión 3 ahora escriben primero la clave en `data-testid="api-key"`. La clave se lee de la
  variable `E2E_API_KEY`, que pone la verificación; nunca va escrita en la prueba.
- Una clave equivocada muestra «Clave inválida».

## Configuración nueva

| Variable | Por omisión | Para qué |
| --- | --- | --- |
| `ENVIRONMENT` | `development` | Con `production` se aplican las reglas de compliance |
| `API_KEYS` | vacía | Clientes y claves (secreto) |
| `RATE_LIMIT_PER_MINUTE` | `30` | Peticiones por cliente por minuto |

## Cómo se comprueba

- `verification unit`, `contract`, `qa`, `e2e` y `evaluate`, como en la sesión 3, ahora con clave.
- Una persona aprueba la publicación. Después, `scripts/publish.py` crea el repositorio en GitHub y hace el push.
- `uv run python -m verification production <url>`: la prueba de humo contra Render.
