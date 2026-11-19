# Fábrica del HR Assistant (Módulo 4, sesión 3)

Los agentes construyen el producto en `product/` a partir de la especificación de `spec/`. Las personas dirigen,
aprueban y comprueban: no programan.

- `/factory` corre la fábrica completa.
- `.claude/agents/`: architect, qa-unit, developer, observability, qa-style, costs, qa-e2e.
- `hooks/permissions.py`: cada agente escribe solo en sus carpetas.
- `hooks/activity_log.py`: bitácora de cada herramienta; `scripts/pipeline.py` dibuja el pipeline.
- `verification/`: el código decide si un paso terminó bien, no el agente.

## Reglas

- El orquestador delega: nunca escribe en `product/` (corrige al agente, no su resultado).
- Todo bucle tiene tope: 2 rechazos del plan, 2 correcciones y 2 vueltas de qa-style; después se escala a una persona.
- Una persona aprueba el plan antes de que se escriba código.
- Nunca leas `.env`.
- Código en inglés; comentarios, docstrings, documentos y mensajes a las personas en español. Sin emojis.
  Es una excepción acordada a QA.md, que pide todo en inglés: no la reportes como incumplimiento.
