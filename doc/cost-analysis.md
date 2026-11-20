# Análisis de costos

Costo por petición, efecto de los reintentos y efecto de las palancas. Las cifras las entregó el
agente `costs`; este documento no agrega ninguna. Todo lo que no tiene cifra está marcado como
**no medido**.

## Fuente y límites de las cifras

- Precios: `data/model_prices.json`, en USD por millón de tokens, revisados el 2026-11-04.
- Los tokens son de **preguntas simuladas**, no una medición real. `scripts/cost_real.py` las
  reemplazará con el costo real de las dos configuraciones (`output/cost-real.md`).
- Las cifras de abajo son un cálculo `tokens x precio`, no una factura.

| Modelo | Nombre en el gateway | Entrada (USD/M) | Salida (USD/M) |
| --- | --- | --- | --- |
| small | `@cf/meta/llama-3.1-8b-instruct-fast` | 0.045 | 0.384 |
| large | `@cf/meta/llama-3.3-70b-instruct-fp8-fast` | 0.293 | 2.253 |

## Costo por petición

| Pregunta | Tokens (entrada/salida) | small (USD) | large (USD) | large / small |
| --- | --- | --- | --- | --- |
| «¿Quién es EMP-0004?» | 29 / 23 | 1.0137e-05 | 6.0316e-05 | 5.95x |
| «Lista el departamento de Ventas» | 34 / 24 | 1.0746e-05 | 6.4034e-05 | 5.96x |

Por 1000 peticiones del tipo «¿Quién es EMP-0004?»: small cerca de 0.0101 USD y large cerca de
0.0603 USD.

`cost_usd` en `/ask` es el costo de las llamadas no cacheadas de la respuesta (ADR 0009).

## Efecto de los reintentos

Con `MODEL_MAX_RETRIES` (por omisión 2) el gateway reintenta timeouts y errores 5xx con espera
exponencial; un 4xx no se reintenta (ADR 0015, `app/gateway.py`).

### Sobre el costo

- `cost_usd` es el de la llamada que respondió. Los intentos fallidos no entregan tokens, así que
  no se suman. Lo cubre `tests/test_gateway_retries.py::test_failed_attempts_do_not_add_to_the_cost_of_the_answer`.
- **Suposición sin medir:** que un 5xx o un timeout no se factura en el gateway. Hay que
  confirmarlo con `scripts/cost_real.py`.

### Sobre la latencia

Peor espera añadida por las esperas entre intentos: `0.5 * (2^n - 1)` segundos, sin contar la
duración de cada intento (el timeout de cada llamada es de 30 s).

| `MODEL_MAX_RETRIES` (n) | Espera añadida en el peor caso |
| --- | --- |
| 0 | 0 s |
| 2 (omisión) | 1.5 s |
| 3 | 3.5 s |

Con el SLO de p95 de 2000 ms, dos reintentos agotados consumen el 75 % del presupuesto solo en
esperas (1.5 s de 2 s). Es un **cálculo, no una medición**: falta `verification load` y
`scripts/cost_real.py`.

### Sobre la carga

Con una falla persistente, cada petición hace `1 + n` llamadas al gateway: 3 con la omisión. Es
carga extra hacia el gateway aunque el costo en tokens no crezca.

## Efecto de las palancas

| Palanca | Variable | Efecto | Cifra |
| --- | --- | --- | --- |
| Enrutamiento por largo | `ROUTER_MAX_CHARS=80` | La que más ahorra: las preguntas cortas van a small | cerca de 6x en preguntas cortas (cálculo de la tabla de arriba) |
| Caché del gateway | `CACHE_TTL_SECONDS>0` | Las llamadas con caché se cuentan en `cached_calls` y no se facturan | **no medido** (sin cifra de ahorro) |
| Ventana de historial | `HISTORY_WINDOW=6` | Acota los tokens de entrada | **no medido** por separado |
| Tope de salida | `MODEL_MAX_TOKENS=300` | Acota los tokens de salida | **no medido** por separado |

### Último `evaluate`

| Configuración | Costo (USD) | Tokens de entrada | Calidad |
| --- | --- | --- | --- |
| Línea base (sin palancas) | 0.000918 | 1681 | 100 % |
| Con palancas | 0.000123 | 1111 | 100 % |

La calidad se mantiene en 100 % en ambas. El ahorro de esta corrida no se reparte entre las
palancas: cuánto aporta cada una por separado está **no medido**.

## Pendiente

- Medir el costo real con `scripts/cost_real.py` y reemplazar las cifras simuladas.
- Confirmar si los intentos fallidos se facturan.
- Medir la latencia con reintentos con `verification load`.
- Medir el ahorro de la caché y el de cada palanca por separado.
