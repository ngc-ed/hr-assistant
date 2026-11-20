# 0005. Métricas en memoria por proceso

Estado: aceptado

Ampliado por ADR 0013 y 0014: la métrica `pii_by_type` (ADR 0013) y los rechazos de
salida (ADR 0014) se suman a las métricas de negocio del proceso, con el mismo modelo
en memoria.

## Contexto

Se pide `GET /metrics` con peticiones, tasa de error, latencia p50/p95, tokens y
cumplimiento del SLO de p95. La API es sin estado (ADR 0001) y no hay base de datos
ni servidor de métricas.

## Decisión

Cada proceso lleva sus métricas en memoria (`app/metrics.py`): contadores y una
ventana acotada de las últimas 1000 latencias, protegidos con un `Lock`. El
middleware registra toda petición; el endpoint suma los tokens de cada corrida.
`error_rate` cuenta solo respuestas 5xx. Percentil por rango más cercano. `slo.met`
es `p95 < SLO_P95_MS`. La respuesta incluye el `pid`.

## Consecuencias

- Sin dependencias nuevas ni red; memoria acotada.
- Son datos operativos, no de la conversación: no cambian ninguna respuesta, así que
  ADR 0001 se mantiene.
- Con varias copias cada una reporta lo suyo; agregarlas queda fuera del producto.
- Al reiniciar el proceso las métricas empiezan de cero.
