# 0003. Un solo agente con bucle con tope y herramientas de solo lectura

Estado: propuesto

## Contexto

Un bucle agente-modelo sin límite puede no terminar o gastar tokens sin control. Las
herramientas acceden a datos personales de empleados.

## Decisión

Un único agente con dos herramientas de solo lectura: `get_employee` y
`search_by_department`. Cada vuelta es una llamada al modelo y suma un paso. Si se alcanza
`AGENT_MAX_STEPS` (por omisión 3) sin respuesta, se contesta exactamente
`No pude completar la respuesta. Intenta con una pregunta más concreta.` Una herramienta
desconocida o un JSON inválido se informa al modelo como resultado y consume un paso.

## Consecuencias

- Costo y latencia por pregunta acotados y predecibles.
- Las herramientas no pueden modificar datos.
- Preguntas que necesiten más vueltas que el tope reciben el mensaje de tope; el tope se
  ajusta por configuración.
