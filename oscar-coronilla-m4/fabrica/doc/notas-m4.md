# Notas del Módulo 4 · Agentes en producción

Fábrica de agentes de Claude Code que construye el HR Assistant desde una carpeta vacía y lo lleva hasta Render.
Trabajé en Windows (PowerShell), con toda la fábrica en la raíz del repositorio y una etiqueta de Git por sesión.

## Sesión 1 · Arquitectura

- Construí la fábrica desde una carpeta vacía: 3 agentes (architect, qa-unit, developer), un hook de permisos y
  verificaciones que deciden con su código de salida.
- El hook de permisos lo probé de verdad dentro de Claude Code: bloqueó al developer al intentar editar una prueba
  existente. La primera prueba no servía, porque el archivo no existía y el error ocurría antes de llegar al hook.
- El primer "rojo" no ejecutó ninguna prueba: el verificador terminaba antes por no existir `product/app/`.
  Lección: rojo no siempre es rojo útil; hay que ver por qué falla.
- Windows: el `.gitignore` copiado del PDF traía espacios al inicio de cada línea y no ignoraba nada. Entraron
  `product/`, `output/` y los cachés al primer commit, y tuve que rehacerlo con `--amend`.

## Sesión 2 · Observabilidad

- La fábrica agregó al producto `request_id`, log JSON (sin el texto de las preguntas), auditoría, `/metrics` con
  SLO y trazas en LangSmith. Rastreé una petición de punta a punta con su `request_id`: log, métricas y traza.
- La fábrica también se observa a sí misma: una bitácora de cada herramienta (`activity.jsonl`) y el pipeline de la
  corrida en Mermaid.
- Bug de plataforma: `sorted()` ordena las rutas distinto en Windows (sin distinguir mayúsculas) que en Linux. Lo
  detectó una prueba que exigía un orden exacto; lo corregí en el código para que fuera determinista.
- Hueco de diseño: una falla de pylint en las pruebas se mandaba a un agente que no podía tocarlas. Como persona,
  dirigí la corrección a qa-unit, sin editar nada a mano.
- Un agente corrió una verificación con `| tail`. No afectó el resultado porque el supervisor decidió con sus
  propias compuertas, sin pipe.
- Casi doy por terminada una corrida con un `report.md` viejo de la sesión anterior. Las fechas de los archivos y
  la bitácora mostraron que no había terminado: no hay que creerle a un archivo sin revisar la evidencia.

## Sesión 3 · Costos

- Supervisor con especialistas en paralelo (costs y qa-e2e) y cinco compuertas: unit, contract, qa, e2e y evaluate.
- Agregué al supervisor una regla propia: mandar a qa-unit las fallas de pylint en las pruebas. En la sesión 4 se
  usó de verdad.
- `evaluate` convirtió mi duda del Módulo 3 (cómo fijar límites de costo) en un criterio medible: misma calidad con
  87 % menos costo, y una palanca solo se acepta si el costo baja sin perder calidad.
- Cloudflare exigía gateways autenticados (`401`, código `2009`). Lo aislé capa por capa: el token era válido,
  Workers AI respondía directo y solo fallaba el paso por el gateway. Confirmé la solución a mano con un segundo
  token y la llevé al producto por la vía de la especificación (`CF_AIG_TOKEN`), no editando el código.
- Con la observabilidad completa entendí qué responde cada pieza: el log dice qué pasó, las métricas cuánto y la
  traza cómo, paso a paso (llm → get_employee → llm).

## Sesión 4 · Producción

- Agregué a la especificación `CF_AIG_TOKEN` y `CF_GATEWAY_ID` como secretos de Render. Sin ellos, producción
  habría tenido el mismo 401 de Cloudflare.
- Hueco de seguridad en Windows: el hook del manual solo vigilaba `Bash`, pero en Windows Claude Code usa
  `PowerShell`. Sin mi cambio, publicar sin aprobación y leer `.env` desde la terminal no se habrían bloqueado. Lo
  detecté porque la bitácora de la sesión 2 registra el nombre real de cada herramienta. Agregué pruebas para que
  la corrección no se pierda.
- Rechacé el primer plan con tres decisiones: qa-unit adapta las fixtures con una clave de ejemplo, una sola lista
  de dependencias para que el CI no diverja del entorno local, y los secretos del gateway en `render.yaml`. El
  segundo plan las incorporó y declaró un riesgo aceptado (la imagen lleva librerías de prueba).
- `ENVIRONMENT` estricto: un valor mal escrito impide arrancar (fail closed), en lugar de arrancar sin las reglas de
  compliance.
- La regla de `| tail` se rompió tres veces en el módulo: observability, qa-unit y el propio supervisor (que se
  corrigió solo). Una regla que vive solo en el prompt se rompe; la que vale es la que decide otra capa.
- Mi fábrica tardó más que las de mis compañeros. La bitácora lo explicó: de 10 a 12 segundos por herramienta,
  porque cada una dispara dos hooks que arrancan Python con `uv run`, más el rechazo del plan y una corrección que
  reinició las cinco compuertas.
- La fábrica terminó en ESCALAR A UNA PERSONA: `scripts/publish.py` no encontró `gh` porque no estaba en el `PATH`
  de la terminal de Claude Code. Agregué la ruta, borré el repositorio local a medias y publiqué yo. El escalamiento
  funcionó como debía: la fábrica se detuvo y dijo exactamente qué revisar.
- En Render usé un Environment Group para los secretos. Si una variable existe en el servicio y en el grupo, manda
  la del servicio.
- Producción con el modelo real: respuestas en lenguaje natural, prueba de humo `[OK]` (200, 401 sin clave y 200
  con clave). Una pregunta que ninguna herramienta podía resolver ("¿cuántos se llaman Ana?") respondió con el
  mensaje del tope de pasos, en lugar de inventar.

## Lo que aprendí sobre Windows

En cada sesión apareció una diferencia de plataforma: espacios del PDF en `.gitignore`, el orden de `sorted()`,
`PowerShell` en lugar de `Bash` en los hooks y `gh` fuera del `PATH`. El curso se diseñó en macOS y Linux; hacerlo
funcionar en Windows fue una lección de producción en sí misma: hay que probar en la plataforma real.

## Mejoras que dejaría para la siguiente versión

- Que el hook bloquee cualquier verificación con `|`, para que la regla deje de depender del prompt.
- Que los hooks llamen directo a `.venv\Scripts\python.exe` en lugar de `uv run`, para ahorrar segundos en cada
  herramienta.
- Separar `requirements.txt` (producción) y `requirements-dev.txt` (pruebas) para una imagen Docker más ligera.
- Cambiar `InMemorySaver` por un checkpointer en disco, para no perder una corrida si se reinicia la computadora.
- Una herramienta `search_by_name`, pedida por especificación, para preguntas por nombre.

## Reflexión del módulo

**Qué cambió en cómo entiendo un agente.** Me quedo con el cambio de paradigma: como programador ya no me enfoco
en escribir el código del producto, sino en entender el requerimiento y en diseñar la estructura de agentes, cada
uno con una tarea puntual, que lo desarrollan. El profesor lo resumió así: antes nos preocupábamos por aprender
lenguajes y sintaxis; ahora hay que aprender a armar la fábrica y dejar que los agentes se encarguen del código.

**La decisión de diseño más valiosa.** La IA puede generar cualquier código, pero la pregunta es a qué costo. Por
eso me parece de gran valor una fábrica que delimite el costo: agentes con tareas acotadas, topes de pasos y de
tokens, y una evaluación que solo acepta una palanca de ahorro si no empeora la calidad. La seguridad también es
muy valiosa, pero todavía me pierdo en cómo se aplica: en el módulo se definió a partir del conocimiento de
expertos, y es un tema que quiero estudiar más a fondo.

**Qué usaría primero en mi trabajo.** Quiero construir mi propia fábrica de apoyo para mi trabajo. La de este módulo
me parece más viable y manejable que la del Módulo 3: hay que identificar dónde se configuran sus características
(especificación, convenciones, agentes y verificaciones) según el desarrollo en el que la monte.

**Lo que me falta.** Con 5 horas por módulo y los retos después, muchas veces seguí las instrucciones para no
quedarme atrás del profesor, sin entender del todo qué hacía cada pieza. Para asimilarlo necesito practicar en
piezas pequeñas y llevarlo a mi trabajo real.
