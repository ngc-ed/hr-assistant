# 0011. Límite de peticiones por cliente por minuto

Estado: aceptado

## Contexto

Un cliente malicioso o defectuoso podría hacer millones de peticiones, agotando
recursos. Es necesario un freno predecible y equitativo.

## Decisión

Cada cliente tiene un límite de `RATE_LIMIT_PER_MINUTE` peticiones (por omisión 30, entero
positivo) en una ventana móvil de 60 segundos. Si lo excede, la API responde
`429 {"detail": "rate limit exceeded"}` con el encabezado `Retry-After` con el número de
segundos que falta para que expire la ventana.

El contador es por proceso, en memoria. El reloj se inyecta para que las pruebas sean
deterministas. No hay persistencia entre reinicios.

## Consecuencias

- El límite es local: con múltiples procesos, cada uno cuenta por separado. Para sincronizar
  límites globales se necesitaría Redis o similar.
- Un cliente que alcanza el límite ve un `429` inmediato y puede reintentar después del
  tiempo indicado en `Retry-After`.
- Las pruebas pueden manipular el reloj para forzar el reinicio de la ventana.
- No existe un valor que desactive el límite: `RATE_LIMIT_PER_MINUTE` debe ser mayor que 0.
