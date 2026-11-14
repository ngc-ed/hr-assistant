# Lista de compliance

Reglas que el producto revisa solo. Las reglas 1 a 5 se aplican al arrancar con
`ENVIRONMENT=production`: si alguna falla, el producto no arranca y `load_settings()`
lanza `ValueError` con un mensaje que nombra la entrada y su largo, nunca su valor.
Las reglas 6 a 9 valen en cualquier ambiente.

| # | Regla | Dónde está en el código | Cómo se comprueba |
| --- | --- | --- | --- |
| 1 | `API_KEYS` no puede estar vacía | `app/config.py`, `_validate_production_compliance()` | `tests/test_config_production.py`: con `API_KEYS` vacía el arranque falla |
| 2 | Cada clave tiene 16 caracteres o más | `app/config.py`, `_validate_production_compliance()` | `tests/test_config_production.py`: una clave corta falla; el mensaje trae el cliente y el largo, no la clave |
| 3 | `MODEL_PROVIDER` no puede ser `fake` | `app/config.py`, `_validate_production_compliance()` | `tests/test_config_production.py`: con `fake` el arranque falla |
| 4 | Si hay `LANGSMITH_API_KEY`, `HIDE_INPUTS` debe valer `true` | `app/config.py`, `_validate_production_compliance()` | `tests/test_config_production.py`: con la clave y `HIDE_INPUTS=false` el arranque falla |
| 5 | Si hay `LANGSMITH_API_KEY`, `HIDE_OUTPUTS` debe valer `true` | `app/config.py`, `_validate_production_compliance()` | `tests/test_config_production.py`: con la clave y `HIDE_OUTPUTS=false` el arranque falla |
| 6 | Cada cliente tiene un límite de `RATE_LIMIT_PER_MINUTE` peticiones por minuto; pasado el límite se responde `429` con `Retry-After` | `app/rate_limiter.py`, `RateLimiter.check_rate_limit()`; middleware en `app/main.py` | `tests/test_rate_limiter.py` y los escenarios de `tests/features/production.feature`, con el reloj inyectado |
| 7 | La clave de API se compara en tiempo constante | `app/auth.py`, `validate_api_key()` con `hmac.compare_digest()` | `tests/test_auth.py` |
| 8 | La clave de API no se escribe en el log | `app/logs.py`, `app/auth.py` (el log solo recibe el nombre del cliente) | Pendiente: ninguna prueba lee el log para comprobar que la clave no aparece. `qa-style` pidió agregarla |
| 9 | La clave de API no llega a las trazas | `app/tracing.py` (los metadatos llevan solo `request_id`) | Pendiente: ninguna prueba lo comprueba. Hoy se sostiene por diseño, no por prueba |

## Criterio de las reglas 4 y 5

La especificación pide aplicarlas cuando las trazas están encendidas. El código las
aplica cuando existe `LANGSMITH_API_KEY` (no vacía), sin mirar `LANGSMITH_TRACING`. Es
más estricto: basta con que la clave esté en el entorno para exigir `HIDE_INPUTS=true`
y `HIDE_OUTPUTS=true`. Quien encienda las trazas siempre tiene esa clave, así que el
caso de la especificación queda cubierto.

## Verificación

```bash
uv run python -m verification unit
```

Corre todas las pruebas con cobertura de 80 % o más. Las reglas 8 y 9 seguirán sin
prueba hasta que se agreguen las pruebas pendientes.
