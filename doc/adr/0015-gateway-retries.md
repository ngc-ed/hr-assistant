# 0015. Reintentos con espera exponencial en el gateway

Estado: aceptado

## Contexto

El gateway puede dar timeout o `5xx` de forma pasajera. Hoy cualquier falla termina en
`502`. Un `4xx` indica un error nuestro (token, cuerpo) y reintentarlo no ayuda.

## Decisión

`GatewayModel` reintenta solo ante timeout o `5xx`, hasta `MODEL_MAX_RETRIES` veces, con
espera de 0.5 s, 1 s, 2 s... La espera es una función `sleep` inyectada (como `Clock`),
de modo que las pruebas no esperan. Al agotar los reintentos se lanza el mismo
`ModelUnavailableError`, que produce el `502` de siempre. Un `4xx` falla de inmediato.
Los intentos fallidos no traen `usage`, así que `cost_usd` es el de la llamada que
respondió y no hay doble cobro. Cada reintento se registra con el tipo de falla y el
número de intento, nunca con URL, encabezados ni token.

## Consecuencias

- La latencia p95 sube cuando el gateway falla: con 2 reintentos suma hasta 1.5 s de
  espera más las llamadas. Se vigila contra el SLO en el tablero.
- Con `timeout` de 30 s por intento, el peor caso es largo; `costs` debe medirlo.
- La espera bloquea un hilo de trabajo del worker; se acepta con pocos reintentos.
- Los reintentos pueden multiplicar la carga sobre un gateway ya degradado.
