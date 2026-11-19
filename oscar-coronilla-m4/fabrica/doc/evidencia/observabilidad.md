# Evidencia · Observabilidad

El producto responde con datos la pregunta «¿qué pasó con la petición X?». Cada petición lleva un `request_id`
que la conecta en la página, el log, la auditoría, las métricas y la traza.

## Los tres pilares

| Pilar | Qué responde | Dónde se ve |
| --- | --- | --- |
| **Log estructurado** (JSON, una línea por evento) | **Qué** pasó: `request`, `agent_run`, `audit`, `pii_detected` y `error`, con `ts`, `service`, `request_id` y `client` | Render > Logs (captura `05`) |
| **Métricas** (`GET /metrics`) | **Cuánto**: peticiones, tasa de errores, latencia p50/p95, tokens, costo, cumplimiento del SLO y contadores de PII | Captura `08` |
| **Trazas** (LangSmith, proyecto `hr-assistant-prod`) | **Cómo**: cada corrida del agente con sus pasos (`llm` → herramienta → `llm`), su latencia y sus metadatos (`request_id`, `client`, `pii_types`) | Capturas `04`, `06` y `07` |

El log nunca registra el texto de las preguntas ni de las respuestas, las claves o los datos personales: solo su
largo, sus tipos o un identificador. Las trazas ocultan entradas y salidas (`HIDE_INPUTS` y `HIDE_OUTPUTS`).

## Trazabilidad de punta a punta: un ejemplo real

La pregunta con un correo del 17 de noviembre tiene el `request_id` `2dce67b8-a081-4b1d-92d4-e299d1a07d63`:

1. **La página** muestra el mensaje de datos sensibles y ese `request_id` (captura `02`).
2. **El log** tiene el evento `pii_detected` con `"client": "hr-portal"`, `"where": "input"` y
   `"types": ["email"]`, y el evento `request` con `POST /ask` → `422` en 2.8 ms (captura `05`).
3. **LangSmith** tiene la traza `pii_input` de 0.00 s, sin llamada al modelo (captura `04`).

Con el id que da un usuario se reconstruye la petición completa sin ver ningún dato sensible.

## Métricas técnicas y de negocio

| Tipo | Métricas |
| --- | --- |
| Técnicas | Latencia p50/p95 (SLO: p95 menor a 2000 ms), tasa de errores, volumen de peticiones, tokens |
| De negocio | Costo por respuesta y acumulado, peticiones por cliente, preguntas bloqueadas por PII, respuestas enmascaradas |

LangSmith muestra además el uso de cada herramienta en los últimos 7 días: `get_employee` 77 % y
`search_by_department` 23 % (captura `06`). Los usuarios preguntan más por personas que por departamentos.

En la prueba de concurrencia sobre la versión final, el p95 fue de 1465 ms: dentro del SLO.

## Dashboards

- **LangSmith Monitoring** (captura `06`): volumen, latencia y errores del proyecto.
- **Dashboard propio «HR Assistant · producción»** (captura `07`): latencia del agente, errores, PII bloqueada y
  trazas por cliente.
- **Cloudflare AI Gateway Analytics** (captura `09`): peticiones, tokens y costo real del modelo.

## La fábrica también se observa

- `output/activity.jsonl` registra cada herramienta de cada agente: quién, qué, cuándo y si salió bien.
- `scripts/pipeline.py` dibuja la corrida en `output/pipeline.md`, con los segundos de cada paso.

## Depurar con estos datos: casos reales

- **Un `502` en producción** se diagnosticó con su `request_id`: la traza mostraba `gateway returned status 401`.
  Pruebas mínimas aislaron la causa (el gateway de Cloudflare exige un segundo token) y se corrigió por la
  especificación (`CF_AIG_TOKEN`).
- **Una corrida de la fábrica interrumpida por un reinicio** se retomó leyendo la bitácora: el último evento decía
  en qué paso estaba.

## Limitaciones

- Las métricas de `/metrics` viven en la memoria del proceso: se reinician con cada despliegue o cuando Render
  duerme el servicio. Para series largas se usan LangSmith y Cloudflare.
- El plan gratuito de LangSmith conserva las trazas 14 días.
