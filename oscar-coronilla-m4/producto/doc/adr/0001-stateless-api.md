# 0001. API sin estado con historial en el cliente

Estado: propuesto

## Contexto

El HR Assistant debe escalar corriendo más copias del proceso. Si el servidor guarda
conversaciones, cada copia tendría un historial distinto y haría falta afinidad de sesión o
un almacén compartido.

## Decisión

La API no guarda nada entre peticiones. El navegador mantiene el historial y lo envía en
`history` en cada `POST /ask`. El agente, el modelo y el directorio no tienen estado mutable;
los datos de empleados son de solo lectura.

## Consecuencias

- Escalar es lanzar más procesos detrás de un balanceador, sin coordinación.
- El cliente controla el historial: hay que validarlo (roles permitidos) y el tamaño de la
  petición crece con la conversación.
- Recargar la página borra la conversación; es aceptable en esta sesión.
