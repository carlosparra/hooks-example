# Fábrica del HR Assistant · Módulo 4 (sesiones 1 a 4)

Una fábrica de agentes de Claude Code construye el producto **HR Assistant** (un asistente de Recursos Humanos) a
partir de la especificación de `spec/` y lo lleva hasta producción. Las personas dirigen, aprueban y comprueban: no
programan el producto.

| Paso | Quién | Patrón |
| --- | --- | --- |
| Plan y ADR | `architect`, y tú lo apruebas | Plan y ejecución, humano en el lazo |
| Pruebas antes del código (TDD y BDD) | `qa-unit` | |
| Seguridad, despliegue y pruebas e2e **al mismo tiempo** | `security`, `deploy` y `qa-e2e` | Multiagente: supervisor con especialistas en paralelo |
| unit → contract → qa → e2e → evaluate | El supervisor decide quién corrige cada fallo (máximo 2) | Encadenamiento con compuertas |
| Revisión contra QA.md | `qa-style` (máximo 2 vueltas) | Evaluador-optimizador |
| Publicar | Tú lo apruebas; `scripts/publish.py` hace el push | Humano en el lazo |
| Prueba de humo en Render | `verification production`; si falla, `triage` decide quién corrige | Triage (máximo 2 ciclos) |

| Sesión | Qué agrega al producto | Etiqueta en Git |
| --- | --- | --- |
| 1 · Arquitectura | API sin estado, agente con tope de pasos, modelo simulado, página web | `sesion01` |
| 2 · Observabilidad | `request_id`, log JSON, auditoría, `/metrics` con SLO, trazas en LangSmith | `sesion02` |
| 3 · Costos | Modelo real (Cloudflare AI Gateway), 4 palancas de costo y costo por respuesta | `sesion03` |
| 4 · Producción | Clave por cliente, límite de peticiones, compliance como código, Docker, CI y Render | `sesion04` |

## Reglas de la fábrica

| Regla | Qué la hace cumplir |
| --- | --- |
| El modelo propone y el código decide | El código de salida de `verification` |
| Quien escribe el código no escribe sus pruebas | El hook `hooks/permissions.py` (código 2 = bloqueado) |
| Todo bucle tiene tope | El skill `/factory`: 2 intentos y se escala a una persona |
| Una persona aprueba lo irreversible | La aprobación del plan y de la publicación (`output/approved.txt`) |
| Los secretos no pasan por la fábrica | Nadie lee `.env`: `permissions.deny` y el hook, también desde la terminal |

## Preparar (una vez)

```bash
uv venv --python 3.12
uv pip install -r requirements.txt
uv run playwright install chromium
uv run python scripts/verify.py
```

En Windows son los mismos comandos en PowerShell. No actives otro entorno virtual en la misma terminal: `uv run`
usa el `.venv` de esta carpeta. Para publicar también necesitas la CLI de GitHub (`gh auth login`), Docker y cuentas
de Cloudflare y Render.

## Correr la fábrica

La primera vez que abres `claude` en esta carpeta responde que sí a **«Do you trust the files in this folder?»**.
Sin esa confianza, Claude Code ignora los permisos de `.claude/settings.json`.

```bash
claude
```

Dentro de Claude Code escribe `/factory <nombre-del-repositorio>`, por ejemplo `/factory hr-assistant-oscar`. Ese
nombre es el del repositorio privado en GitHub y el del servicio en Render: usa uno que no exista en tu cuenta.

La fábrica pregunta dos veces: si apruebas el plan y si publica. `--aprobar` solo aprueba el plan; publicar
siempre se pregunta. Al terminar deja en `output/` el reporte (`report.md`), la revisión de QA (`qa-review.md`), la
bitácora de cada herramienta (`activity.jsonl`) y el pipeline de la corrida (`pipeline.md`, con un diagrama
Mermaid).

## Comprobar en local

```bash
uv run python -m verification unit
uv run python -m verification contract
uv run python -m verification qa
uv run python -m verification e2e
uv run python -m verification evaluate
```

`evaluate` compara la calidad y el costo de la línea base contra la configuración con palancas: pasa solo si el
costo baja sin perder calidad.

Para abrir la página, desde `product/`:

```bash
uv run uvicorn app.main:app --no-access-log
```

- Página: http://127.0.0.1:8000. Pide la clave de acceso y muestra el `request_id` de cada respuesta.
- Métricas: http://127.0.0.1:8000/metrics (también piden clave).
- Log: una línea JSON por evento en la terminal. Nunca registra el texto de las preguntas ni las claves.

## Modelo real y trazas en local (opcional)

Copia `product/.env.example` a `product/.env` y llénalo **en tu editor** (nunca en el chat ni en el código):

| Variable | Para qué |
| --- | --- |
| `MODEL_PROVIDER=gateway` | Usa Cloudflare en lugar del modelo simulado |
| `CF_ACCOUNT_ID`, `CF_GATEWAY_ID`, `CF_API_TOKEN` | Cuenta, gateway y token de Workers AI |
| `CF_AIG_TOKEN` | Token del gateway, si tu cuenta exige gateways autenticados (error `401` con código `2009`) |
| `API_KEYS` | Clientes y claves, con la forma `cliente:clave` |
| `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY` | Trazas en LangSmith (sin texto: `HIDE_INPUTS`/`HIDE_OUTPUTS` valen `true`) |

```bash
cd product
uv run --env-file .env uvicorn app.main:app --no-access-log
```

Si el modelo real falla, la API responde `502 model unavailable` con su `request_id`: búscalo en el log y en
LangSmith.

## Publicar en producción

1. Al final de `/factory`, la fábrica resume el pipeline de CI, los secretos y el repositorio, y pregunta si publica.
   Con `si` escribe `output/approved.txt` y corre `scripts/publish.py`, que crea el repositorio **privado** y hace
   el push. Sin esa aprobación, el hook bloquea el comando.
2. En GitHub, pestaña **Actions**: las cuatro etapas del CI (`style` → `unit` → `e2e` → `docker`).
3. En Render, **New > Blueprint** y elige el repositorio. El resumen debe decir **Create web service**; si dice
   **Update**, detente.
4. Escribe los secretos en **Render > Environment**, o en un **Environment Group** vinculado al servicio:
   `API_KEYS`, `CF_ACCOUNT_ID`, `CF_API_TOKEN`, `CF_AIG_TOKEN` y `CF_GATEWAY_ID`. Si una variable existe en el
   servicio y en el grupo, manda la del servicio.
5. Cuando el servicio esté **Live**, corre la prueba de humo desde tu terminal. La clave es la parte después de
   `cliente:` y se lee de una variable, nunca del comando ni del chat.

Windows (PowerShell):

```powershell
$env:SMOKE_API_KEY = Read-Host "Clave (sin cliente:)"
uv run python -m verification production https://<tu-servicio>.onrender.com
Remove-Item Env:SMOKE_API_KEY
```

macOS / Linux:

```bash
read -rs SMOKE_API_KEY && export SMOKE_API_KEY
uv run python -m verification production https://<tu-servicio>.onrender.com
unset SMOKE_API_KEY
```

Debe salir `[OK]` en `/health` (200), `/ask` sin clave (401) y `/ask` con clave (200). Si falla, `triage` escribe
`output/triage.md` y decide si corrige `security`, `deploy` o una persona.

El plan gratuito de Render duerme el servicio con la inactividad: la primera petición puede tardar un minuto.

## Notas para Windows

- `setx PYTHONUTF8 1` evita errores de codificación con acentos.
- En Windows, Claude Code usa `PowerShell` como terminal en lugar de `Bash`. El hook vigila las dos.
- Si `scripts/publish.py` falla con `FileNotFoundError` al llamar a `gh`, la CLI de GitHub no está en el `PATH` de
  esa terminal: abre una terminal nueva o agrega `C:\Program Files\GitHub CLI` al `PATH`.
- Copia el código del manual en Markdown, no del PDF: el PDF agrega espacios al inicio de cada línea.

## Qué hay en esta carpeta

| Carpeta | Qué es |
| --- | --- |
| `spec/` | Qué debe hacer el producto (requisitos, no código), precios por modelo y datos |
| `.claude/agents/` | Los diez agentes y sus instrucciones |
| `.claude/skills/factory/` | El supervisor `/factory` |
| `hooks/` | Permisos por agente (escritura, `.env` y publicación) y bitácora de cada herramienta |
| `verification/` | Las compuertas: contrato, QA, e2e, la evaluación de costo y calidad, y la prueba de humo |
| `scripts/` | La lista de QA de la fábrica (`verify.py`), el pipeline (`pipeline.py`) y la publicación (`publish.py`) |
| `tests/` | Las pruebas de la fábrica |
| `doc/` | Las notas del módulo |
| `product/`, `output/` | Lo que generan los agentes (no se sube a git; `product/` se publica en su propio repositorio) |
