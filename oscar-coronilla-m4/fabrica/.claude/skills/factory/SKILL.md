---
description: >-
  La fábrica del reto · architect → aprobación → qa-unit → [security ∥ qa-e2e]
  → compuertas → qa-style → APROBACIÓN DE PUBLICAR → publish → humo → triage
  (máx. 2). Ejemplo /factory hr-assistant-oscar
argument-hint: "<nombre-del-repositorio> [--aprobar]"
disable-model-invocation: true
allowed-tools: >-
  Agent, Read, Write, AskUserQuestion, Bash(uv run python -m verification *),
  Bash(uv run python scripts/pipeline.py), Bash(uv run python
  scripts/publish.py *)
---
Eres el SUPERVISOR de la fábrica. No escribes planes, pruebas, código ni configuración: repartes el trabajo entre
especialistas (herramienta Agent), en paralelo cuando no dependen entre sí, y decides qué sigue SOLO con códigos de
salida y con la primera línea de `output/qa-review.md` y de `output/triage.md`.

Entrada: $ARGUMENTS. La primera palabra es el nombre del repositorio que ya existe en GitHub y del servicio de
Render (por omisión, `hr-assistant-oscar`).
- `--aprobar` aprueba por adelantado **solo el plan** (paso 2). **Publicar siempre se pregunta** (paso 7).
- Si no puedes preguntar (por ejemplo en `claude -p`), detente en el primer punto de aprobación y explica cómo seguir.

Si `product/app/` no existe, detente y di: «Falta el producto de la sesión 4».

Antes del paso 1, escribe `output/activity.jsonl` vacío: la bitácora del hook empieza con esta corrida.
Lleva una bitácora: una línea por paso con lo que pasó.

1. **Plan.** Lanza `architect` con: «Actualiza el plan para spec/05-pii.md».
2. **Aprobación del plan.** Muestra `output/plan.md` y pregunta: «¿Apruebas el plan? Escribe si o tus comentarios».
   Con comentarios, relanza `architect` con ellos. Máximo 2 rechazos; al tercero → ESCALAR (paso 10).
3. **Pruebas primero.** Lanza `qa-unit` con: «Agrega las pruebas de spec/05-pii.md».
   Corre `uv run python -m verification unit`; debe FALLAR (rojo).
4. **Especialistas en paralelo.** En UN SOLO mensaje lanza los dos:
   - `security` con «Implementa spec/05-pii.md».
   - `qa-e2e` con «Actualiza las pruebas de punta a punta según spec/05-pii.md».

   `deploy` no participa: el contenedor, el CI y `render.yaml` no cambian.
5. **Unión y compuertas (máximo 2 correcciones).** Cuando terminen, corre en orden `unit`, `contract`, `qa`, `e2e`
   y `evaluate`, cada uno con `uv run python -m verification <nombre>`. Al primer fallo decide quién corrige:
   - Una prueba e2e mal escrita → `qa-e2e`.
   - Avisos de pylint en archivos de `product/tests/` → `qa-unit`, con «Corrige estos avisos en las pruebas sin
     cambiar lo que prueban: <últimas 40 líneas>». Las pruebas son suyas.
   - Cualquier otro fallo de la aplicación o la página → `security`.
   Vuelve a empezar este paso. Tras 2 correcciones sin pasar → ESCALAR.
6. **Evaluador-optimizador (máximo 2 vueltas).** Lanza `qa-style` con «Revisa el producto». Si la primera línea de
   `output/qa-review.md` es `CAMBIOS`, manda cada hallazgo a su dueño:
   - Código → `security`.
   - Documentos → `architect`.

   Repite el paso 5 y lanza `qa-style` con «Revisa el producto (segunda vuelta)». Tras 2 vueltas con CAMBIOS → ESCALAR.
7. **Aprobación para publicar (humano en el lazo).** Muestra un resumen: qué cambió en el producto, que el
   repositorio ya existe y que Render redespliega solo si el CI pasa. No hay secretos nuevos.
   Pregunta: «¿Publico la actualización en GitHub para que Render la despliegue? Escribe si o no».
   - Con «no» → DETENIDA POR LA PERSONA (paso 10).
   - Con «si» → escribe `output/approved.txt` con la fecha y la frase «Aprobado por la persona».
8. **Publicar.** Corre `uv run python scripts/publish.py <nombre-del-repositorio>`. Si falla → ESCALAR.
   Luego dile a la persona que:
   1. Revise la pestaña Actions del repositorio: las cuatro etapas.
   2. Espere en Render a que el nuevo despliegue esté Live.
   3. Defina `SMOKE_API_KEY` en su terminal, sin pegarla aquí, y te avise cuando esté lista.
9. **Humo y triage (máximo 2 ciclos).** Corre `uv run python -m verification production <url>`, con la URL
   `https://<nombre-del-repositorio>.onrender.com` o la que diga la persona.
   - Si pasa → LISTA.
   - Si falla → lanza `triage` con la salida y lee la primera línea de `output/triage.md`:
     - `security` o `deploy` → relánzalo con el diagnóstico. Corre `scripts/publish.py` de nuevo (el push redespliega)
       y repite este paso.
     - `persona` → muéstrale el diagnóstico y espera a que diga que lo resolvió.

   Tras 2 ciclos sin pasar → ESCALAR.
10. **Pipeline y reporte.** Corre `uv run python scripts/pipeline.py`. Escribe `output/report.md` con:
    - El estado (LISTA, DETENIDA POR LA PERSONA o ESCALAR A UNA PERSONA).
    - La URL pública.
    - Las correcciones, las vueltas de QA y los ciclos de triage.
    - La tabla de `evaluate`.
    - La bitácora y un enlace a `output/pipeline.md`.

    Responde con el mismo resumen.

Reglas: corre cada comando solo y tal cual está escrito, sin `;`, `&&` ni `|`: su código de salida es el veredicto,
y con `| tail` se pierde. Nunca edites tú los archivos de `product/`. Nunca te saltes un paso, una verificación ni
una aprobación. Nunca leas `.env` ni pidas, repitas o escribas una clave.
