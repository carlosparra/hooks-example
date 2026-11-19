# Evidencia · Optimización de costos

El producto usa Cloudflare Workers AI a través de AI Gateway. Los precios por modelo están en
`spec/model_prices.json` (USD por millón de tokens, tomados de la página de precios de Cloudflare). Cada respuesta
reporta su `cost_usd`, y `/metrics` acumula el costo del proceso.

## Las cuatro palancas

| Palanca | Cómo funciona | Configuración |
| --- | --- | --- |
| 1 · Enrutamiento de modelos | Una regla en código (no otro modelo) elige el modelo por pregunta: las simples van al modelo pequeño; las largas o con «compara», «resume», «explica», «por qué», «analiza» o «todos», al grande | `ROUTING=true`, `ROUTER_MAX_CHARS=80`, `MODEL_SMALL`, `MODEL_LARGE` |
| 2 · Ventana de historial | Al modelo solo se mandan los últimos mensajes de la conversación | `HISTORY_WINDOW=6` |
| 3 · Tope de salida | Límite de tokens de cada respuesta | `MODEL_MAX_TOKENS=300` |
| 4 · Caché del gateway | AI Gateway responde desde caché las peticiones repetidas; una respuesta cacheada no cuesta | `CACHE_TTL_SECONDS` (0 = apagada) |

Precios usados (USD por millón de tokens): modelo pequeño `llama-3.1-8b-instruct-fast`, 0.045 de entrada y 0.384 de
salida; modelo grande `llama-3.3-70b-instruct-fp8-fast`, 0.293 de entrada y 2.253 de salida. El modelo grande cuesta
unas 6 veces más.

## Evidencia: línea base contra palancas

`uv run python -m verification evaluate` corre el set de evaluación (`verification/eval_set.json`, 8 preguntas que
incluyen un empleado inexistente y una fuera de alcance) dos veces, con 10 mensajes de historial por pregunta, como una
conversación larga. La línea base apaga el enrutamiento y la ventana.

| Configuración | Calidad | Costo (USD) | Tokens de entrada |
| --- | --- | --- | --- |
| Línea base (`ROUTING=false`, sin ventana) | 100 % | 0.000867 | 1661 |
| Con palancas (configuración por omisión) | 100 % | 0.000114 | 1091 |
| **Diferencia** | **sin pérdida** | **−86.9 %** | **−34.3 %** |

La verificación es una compuerta de la fábrica: **una palanca solo se acepta si el costo baja y la calidad no**. Si
una configuración nueva abarata pero falla alguna pregunta del set, la fábrica no la publica.

## Evidencia en producción

| Medición | Resultado |
| --- | --- |
| 20 preguntas reales con el modelo real (16 y 17 de noviembre) | 0.000769 y 0.000779 USD: unos **0.000039 USD por pregunta** (≈ 3.9 USD por cada 100 000 preguntas) |
| 40 peticiones `429` por pasar el límite por cliente | **0 USD**: las peticiones rechazadas no llegan al modelo |
| Preguntas bloqueadas por contener PII | **0 USD**: se rechazan antes de llamar al modelo (en LangSmith, la traza `pii_input` dura 0.00 s) |

Los controles de seguridad también son controles de costo: el límite por cliente y el bloqueo de PII impiden gastar
en peticiones que no deben llegar al modelo.

## Trade-offs

| Palanca | Lo que se gana | Lo que se arriesga | Cómo se mitiga |
| --- | --- | --- | --- |
| Enrutamiento | El modelo pequeño cuesta unas 6 veces menos | Una pregunta compleja mal clasificada puede recibir una respuesta pobre | Palabras clave y largo envían lo complejo al modelo grande; la regla es código determinista y tiene pruebas |
| Ventana de historial | Menos tokens de entrada en conversaciones largas | El modelo no ve mensajes antiguos | La API es sin estado y las preguntas de RH suelen ser autocontenidas; la ventana es configurable |
| Tope de salida | Acota el costo de cada respuesta | Una respuesta larga podría cortarse | 300 tokens sobran para las respuestas del directorio |
| Caché | Las preguntas repetidas no cuestan | Una respuesta puede quedar desactualizada mientras dure el TTL | Apagada por omisión; se enciende solo si los datos cambian poco |

## Limitaciones

- `evaluate` usa el modelo simulado con los precios reales: mide con exactitud el efecto del enrutamiento y de la
  ventana en tokens y costo, pero no la calidad del modelo pequeño real. La calidad en producción se comprobó con
  preguntas reales del set (capturas en esta carpeta).
- La caché del gateway está implementada, pero no se midió su ahorro en este reto porque está apagada por omisión.
