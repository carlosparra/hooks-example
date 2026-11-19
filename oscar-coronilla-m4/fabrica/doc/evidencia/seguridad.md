# Evidencia · Seguridad y controles

Los controles están en dos niveles: en el **producto** (lo que protege al HR Assistant en producción) y en la
**fábrica** (lo que impide que los agentes que lo construyen hagan algo indebido). Ningún control depende de que
el modelo obedezca: los decide código.

## Requisitos del reto

| Requisito | Cómo se cumple | Evidencia |
| --- | --- | --- |
| Validación de inputs | Pregunta vacía o de más de `MAX_QUESTION_CHARS` → `422`; el `X-Request-ID` que manda el cliente se valida antes de usarlo en el log; la PII en la pregunta o el historial se rechaza | Pruebas de contrato de las sesiones 1, 2 y del reto |
| Validación de outputs | La respuesta del modelo debe ser texto no vacío, se recorta a `OUTPUT_MAX_CHARS` y la PII se enmascara antes de responder; la página pinta las respuestas con `textContent`, nunca con `innerHTML` | `app/guardrails.py`, campo `pii_masked` |
| Gestión de secretos | Ningún secreto en el código: viven en Render > Environment con `sync: false`; `.env` está en `.gitignore`; las verificaciones leen claves de variables, nunca del comando | `render.yaml`, `.gitignore` |
| Registro de auditoría | Eventos `audit` (cada herramienta del agente) y `pii_detected`, con `request_id` y `client`; nunca la clave, el texto de la pregunta ni el dato sensible | Captura `05-render-pii-detected.png` |
| Detección de PII | Correo, teléfono, CURP, RFC, tarjeta (Luhn) y CLABE: bloqueo en la entrada (`422`, sin llamar al modelo) y enmascaramiento en la salida | Capturas `02` a `05`; contrato del reto |
| Mínimo privilegio | Una clave por cliente; los agentes de la fábrica solo escriben en sus carpetas; el CI corre con permiso de solo lectura; el repositorio del producto es privado; la clave de LangSmith es de solo trazas | Ver abajo |

## Controles del producto

| # | Control | Qué evita |
| --- | --- | --- |
| 1 | **Clave por cliente** (`X-API-Key`), comparada con `hmac.compare_digest` | Acceso sin autorización; adivinar la clave midiendo tiempos de respuesta |
| 2 | **Límite de peticiones por cliente** (30 por minuto, `429` con `Retry-After`) | Abuso y gasto descontrolado: 40 peticiones rechazadas costaron 0 USD |
| 3 | **Detección de PII en la entrada** | Que un dato personal llegue al modelo, a Cloudflare o a LangSmith |
| 4 | **Enmascaramiento de PII en la salida**, antes de recortar | Que una respuesta muestre un dato personal, ni siquiera a medias |
| 5 | **Validación de entrada y de salida** | Peticiones vacías o enormes; respuestas vacías o desbordadas |
| 6 | **Auditoría sin datos sensibles** | Que el propio log se convierta en una fuga |
| 7 | **Trazas sin texto** (`HIDE_INPUTS` y `HIDE_OUTPUTS` en `true`) | Que LangSmith guarde preguntas o respuestas |
| 8 | **Compliance como código:** con `ENVIRONMENT=production` el servicio **no arranca** si el modelo es el simulado, si hay claves de menos de 16 caracteres, si las trazas no ocultan el texto o si `PII_DETECTION` no vale `true` | Que una configuración insegura llegue a producción por descuido |
| 9 | **Fail closed:** un valor de `ENVIRONMENT` mal escrito impide arrancar | Que un error tipográfico desactive el compliance |
| 10 | **Errores sin secretos:** una `API_KEYS` mal formada dice qué entrada falla y su largo, nunca su valor | Filtrar una clave en un mensaje de error |
| 11 | **Rotación de credenciales probada:** se rotó `API_KEYS` y se comprobó que la clave anterior responde `401` | Que una clave comprometida siga funcionando |

## Controles de la fábrica

| # | Control | Qué evita |
| --- | --- | --- |
| 12 | **Hook de permisos por agente:** cada agente escribe solo en sus carpetas (el que escribe el código no escribe sus pruebas) | Que un agente se califique a sí mismo o toque lo que no le corresponde |
| 13 | **Nadie lee `.env`**, ni con `Read` ni desde la terminal (`Bash` y `PowerShell`) | Que un agente vea secretos |
| 14 | **Publicar requiere aprobación humana** (`output/approved.txt`), verificada por el hook y por el script; la aprobación vale para una sola publicación | Publicar sin que una persona lo decida |
| 15 | **El agente que prepara el despliegue no puede ejecutar comandos** | Que quien prepara la publicación sea quien la dispara |
| 16 | **CI con compuertas** (estilo, pruebas, e2e y build) y **despliegue solo si el CI pasa** (`checksPass`) | Publicar código que no pasó las pruebas |
| 17 | **Bitácora de cada herramienta de cada agente** (`output/activity.jsonl`) | Que un agente haga algo sin dejar rastro |

## Defensa en capas: un ejemplo real

Una pregunta con un correo pasa por varias capas, y cada una deja evidencia con el mismo `request_id`:

1. La **clave por cliente** identifica a `hr-portal`.
2. El **límite por cliente** cuenta la petición (también las bloqueadas, para que nadie pruebe el detector gratis).
3. El **detector de PII** la rechaza con `422`, sin llamar al modelo.
4. La **auditoría** registra `pii_detected` con `"types": ["email"]`, sin el correo.
5. La **traza** `pii_input` dura 0.00 s: el modelo nunca la vio.

## Limitaciones conocidas

- La detección de PII usa expresiones regulares: no detecta nombres propios ni datos escritos de forma creativa
  (por ejemplo, un correo con «arroba»). Una mejora sería un detector con un modelo de clasificación.
- El límite de peticiones es por proceso; con varias instancias haría falta un almacén compartido (Redis).
- Las claves por cliente viven en una variable de entorno; a mayor escala convendría un gestor de secretos con
  rotación automática.
- En desarrollo, con `HIDE_OUTPUTS=false`, la traza podría guardar una respuesta antes de enmascararla. En
  producción no ocurre, porque el compliance exige ocultar las salidas.
