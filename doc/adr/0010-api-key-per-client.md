# 0010. Autenticación por API Key por cliente

Estado: aceptado

## Contexto

Cada cliente (empresa, usuario) debe autenticarse para usar la API. Los secretos no
deben filtrarse en logs, trazas, ni mensajes de error.

## Decisión

La API exige un encabezado `X-API-Key` en `POST /ask` y `GET /metrics`. La configuración
`API_KEYS` lista pares `cliente:clave` separados por comas (`cliente1:clave1,cliente2:clave2`).

El middleware valida la clave y extrae el nombre del cliente, que se agrega al contexto de
la petición para que el log lo escriba. En producción las claves tienen un mínimo de 16
caracteres (ADR 0012).

Si la clave es inválida o falta, la API responde `401 {"detail": "invalid or missing API key"}`.
Nunca se escribe la clave en el log, en las trazas ni en mensajes de error.

Endpoints públicos sin clave: `GET /`, `GET /health`, `GET /docs`.

Fuera de producción, si `API_KEYS` está vacía el middleware no pide clave, para
facilitar el desarrollo local. En producción una `API_KEYS` vacía impide arrancar.

Advertencia explícita: sin `API_KEYS`, `POST /ask` y `GET /metrics` quedan abiertos, sin
ninguna autenticación, en cualquier entorno que no sea producción. Lo único que lo
impide es `ENVIRONMENT=production`; quien despliegue fuera de producción debe
configurar `API_KEYS` si la API es alcanzable desde una red no confiable.

## Consecuencias

- El log anota el nombre del cliente, no la clave (trazabilidad sin riesgo de exposición).
- El navegador guarda la clave en `sessionStorage`, que se limpia al cerrar la sesión.
- Revocar a un cliente es quitar su entrada de `API_KEYS` en Render, lo que reinicia el
  servicio.
- Con múltiples procesos, cada uno valida de forma independiente.
- La seguridad fuera de producción depende de una variable de entorno: un despliegue
  sin `ENVIRONMENT=production` y sin `API_KEYS` expone la API. El README lo documenta.
