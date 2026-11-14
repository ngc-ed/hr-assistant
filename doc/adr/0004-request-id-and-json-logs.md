# 0004. Id por petición y log JSON sin datos personales

Estado: propuesto

## Contexto

Soporte necesita responder qué pasó con la petición X. Con varias copias del proceso
y un log de texto libre no hay forma de unir los eventos de una misma petición, y
escribir preguntas o respuestas expondría datos de empleados.

## Decisión

Un middleware asigna a cada petición un `request_id`: el del encabezado
`X-Request-ID` si cumple `^[A-Za-z0-9._:-]{1,128}$`, o un UUID nuevo. Se devuelve en
el encabezado de toda respuesta y en el cuerpo de `POST /ask`. Cada evento se escribe
como una línea JSON en stdout (`ts`, `service`, `event`, `request_id`) con eventos
`request`, `agent_run`, `audit` y `error`. El log guarda conteos, nunca el texto de
la pregunta o la respuesta; `error` guarda el tipo de excepción, no el mensaje. La
hora sale de un `Clock` inyectado. El agente informa las herramientas por un callback
y no conoce al logger.

## Consecuencias

- Con un `request_id` se filtran todas las líneas de la petición en cualquier copia.
- Un id del cliente con forma inválida se reemplaza: protege el log, pero el cliente
  debe usar el id que devuelve la respuesta.
- `audit` sí registra los argumentos (ids, departamentos): es su propósito.
- Las pruebas leen el log desde un `StringIO` inyectado y son deterministas.
