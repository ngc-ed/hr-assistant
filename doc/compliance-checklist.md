# Lista de compliance

Reglas que el producto revisa solo. Las reglas 1 a 5 se aplican al arrancar con
`ENVIRONMENT=production`: si alguna falla, el producto no arranca y `load_settings()`
lanza `ValueError` con un mensaje que nombra la entrada y su largo, nunca su valor.
Las reglas 6 a 14 valen en cualquier ambiente.

| # | Regla | Dónde está en el código | Cómo se comprueba |
| --- | --- | --- | --- |
| 1 | `API_KEYS` no puede estar vacía | `app/config.py`, `_validate_production_compliance()` | `tests/test_config_production.py`: con `API_KEYS` vacía el arranque falla |
| 2 | Cada clave tiene 16 caracteres o más | `app/config.py`, `_validate_production_compliance()` | `tests/test_config_production.py`: una clave corta falla; el mensaje trae el cliente y el largo, no la clave |
| 3 | `MODEL_PROVIDER` no puede ser `fake` | `app/config.py`, `_validate_production_compliance()` | `tests/test_config_production.py`: con `fake` el arranque falla |
| 4 | Si hay `LANGSMITH_API_KEY`, `HIDE_INPUTS` debe valer `true` | `app/config.py`, `_validate_production_compliance()` | `tests/test_config_production.py`: con la clave y `HIDE_INPUTS=false` el arranque falla |
| 5 | Si hay `LANGSMITH_API_KEY`, `HIDE_OUTPUTS` debe valer `true` | `app/config.py`, `_validate_production_compliance()` | `tests/test_config_production.py`: con la clave y `HIDE_OUTPUTS=false` el arranque falla |
| 6 | Cada cliente tiene un límite de `RATE_LIMIT_PER_MINUTE` peticiones por minuto; pasado el límite se responde `429` con `Retry-After` | `app/rate_limiter.py`, `RateLimiter.check_rate_limit()`; middleware en `app/main.py` | `tests/test_rate_limiter.py` y los escenarios de `tests/features/production.feature`, con el reloj inyectado |
| 7 | La clave de API se compara en tiempo constante | `app/auth.py`, `validate_api_key()` con `hmac.compare_digest()` | `tests/test_auth.py` |
| 8 | La clave de API no se escribe en el log | `app/logs.py`, `app/auth.py` (el log solo recibe el nombre del cliente) | `tests/test_production_endpoints.py::TestClientNameInResponse::test_api_key_never_appears_in_the_log`: manda una petición con clave válida y otra con clave inválida, lee el log capturado y comprueba que ninguna de las dos claves aparece |
| 9 | La clave de API no llega a las trazas | `app/tracing.py` (los metadatos llevan solo `request_id`) | Sin prueba propia sobre las trazas. La prueba de la fila 8 cubre el log, no los metadatos de trazas; se sostiene por diseño |
| 10 | La pregunta y el historial se enmascaran (`[CORREO]`, `[TELEFONO]`, `[RFC]`, `[CURP]`, `[NSS]`, `[TARJETA]`) antes de llegar al modelo | `app/pii.py`, `mask_pii()`; `app/main.py`, `_mask_request()` | `tests/test_pii.py` y el escenario de `tests/features/production_ready.feature` donde el modelo espía recibe `[CORREO]` y `[RFC]` |
| 11 | La respuesta se enmascara antes de devolverla | `app/main.py`, `_safe_answer()` (etapa revisor) con `mask_pii()` | Escenario de `production_ready.feature`: la respuesta lleva `[CORREO]` y no el correo |
| 12 | Cada detección deja un evento `pii_detected` con `pii_type`, `count` y `direction`; el valor nunca va al log, a la traza ni a un error. Los `args` del evento `audit` también se enmascaran | `app/pii.py` (solo devuelve conteos); `app/main.py`, `_log_pii()` y `_mask_args()` (callback `audit` de `_run_agent()`) | `tests/test_pii_logging.py`, los pasos de `production_ready.feature` que buscan el valor en el log y `tests/test_multiagent.py::test_audit_arguments_are_masked` |
| 13 | La respuesta no puede venir vacía, pasar de `MAX_ANSWER_CHARS` ni traer PII, algo con forma de clave (`sk-...`, `Bearer ...`, cadena larga aleatoria) o un `EMP-xxxx` inventado | `app/output_guard.py`, `rejection_reason()`; `app/config.py`, `MAX_ANSWER_CHARS` | `tests/test_output_guard.py`, `tests/test_config_production_ready.py` y `tests/test_multiagent.py` (`invented_id`) |
| 14 | Una respuesta rechazada se cambia por «No pude generar una respuesta segura. Intenta de nuevo.» con `200` y se registra `output_rejected` con el motivo, sin el texto | `app/main.py`, `_safe_answer()` | Escenario de `production_ready.feature` con `sk-...`: mensaje seguro, motivo `secret` y la clave ausente del log |

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

Corre todas las pruebas con cobertura de 80 % o más. La regla 9 sigue sin prueba
propia sobre las trazas.
