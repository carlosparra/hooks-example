# 0012. Compliance al arrancar y publicación solo con CI verde

Estado: propuesto

## Contexto

Una configuración insegura en producción (modelo simulado, claves cortas, trazas con datos
personales) no debe depender de que alguien la revise a mano. Tampoco debe llegar a Render un
cambio que no pasó las pruebas.

## Decisión

Con `ENVIRONMENT=production`, `create_app` llama a `compliance.enforce` antes de construir nada
y el proceso no arranca si `MODEL_PROVIDER=fake`, si `API_KEYS` está vacía o tiene una clave de
menos de 16 caracteres, o si las trazas están pedidas sin `HIDE_INPUTS` y `HIDE_OUTPUTS`. El
error nombra las reglas, nunca valores. `ENVIRONMENT` solo acepta `development` y `production`.
`doc/compliance-checklist.md` enlaza cada regla con su código y su prueba. El producto se
empaqueta con `Dockerfile` (`python:3.12-slim`, usuario sin root), el CI encadena `style`,
`unit`, `e2e` y `docker`, y `render.yaml` usa `autoDeployTrigger: checksPass`, con los secretos
en `sync: false`.

## Consecuencias

- Un despliegue mal configurado falla en el arranque y Render conserva la versión anterior.
- Los secretos viven solo en Render; el repositorio no tiene ninguno.
- Publicar requiere CI verde y la aprobación de una persona; un cambio urgente también pasa
  por el pipeline completo.
