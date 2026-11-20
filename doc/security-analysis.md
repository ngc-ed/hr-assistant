# Análisis de seguridad

Cada control, el riesgo que cubre, dónde está en el código y cómo se comprueba. Las rutas son
relativas a `product/`.

| Control | Riesgo que cubre | Dónde está | Cómo se comprueba |
| --- | --- | --- | --- |
| PII enmascarada (correo, teléfono, RFC, CURP, NSS, tarjeta) en la pregunta, el historial y la respuesta; `mask_pii()` solo devuelve texto y conteos (ADR 0013) | Que datos personales lleguen al modelo, a la respuesta, al log o a la traza | `app/pii.py` (`mask_pii`, `PII_PATTERNS`); `app/main.py` (`_mask_request`, `_safe_answer`) | `tests/test_pii.py` (cada tipo, varios en un texto, EMP-0001 y fechas no se confunden); escenarios de `tests/features/production_ready.feature` (el modelo espía recibe `[CORREO]` y `[RFC]`; la respuesta lleva `[CORREO]`) |
| Validación de salida: no vacía, no más de `MAX_ANSWER_CHARS`, sin PII, sin forma de clave (`sk-...`, `Bearer ...`, cadena larga aleatoria); si falla, `200` con el mensaje seguro (ADR 0014) | Que el modelo devuelva datos sin enmascarar, una clave o texto desmedido | `app/output_guard.py` (`rejection_reason`, `SAFE_ANSWER`); `app/main.py` (`_safe_answer`) | `tests/test_output_guard.py` (los cuatro motivos, `Bearer`, cadena aleatoria, límite exacto); escenario de `production_ready.feature` con `sk-...` (mensaje seguro, motivo `secret`, clave ausente del log) |
| Reintentos acotados: solo timeout o 5xx, hasta `MODEL_MAX_RETRIES`, espera exponencial inyectada, `502` al agotarse, mensaje fijo sin token (ADR 0015) | Cascadas de llamadas al gateway, esperas sin fin y filtración del token en errores | `app/gateway.py` (`GatewayModel.complete`, `_is_retryable`, `ModelUnavailableError`, `REQUEST_TIMEOUT_SECONDS`) | `tests/test_gateway_retries.py` (esperas `[0.5, 1, 2]`, un 4xx no se reintenta, token ausente del error, costo sin duplicar); escenario de `production_ready.feature`: 503 constante termina en `502` con 3 llamadas |
| Claves por cliente: `X-API-Key` validada con `hmac.compare_digest`, `401` sin clave o inválida, la clave nunca en errores ni en el log; en producción `API_KEYS` no vacía y claves de 16 caracteres o más (ADR 0010, 0012) | Acceso anónimo, ataques de tiempo y filtración de claves | `app/auth.py` (`parse_api_keys`, `validate_api_key`); `app/main.py` (`_add_auth_middleware`); `app/config.py` (`_validate_production_compliance`) | `tests/test_auth.py`; `tests/test_production_endpoints.py` (incluye `test_api_key_never_appears_in_the_log` y `test_error_message_does_not_expose_key`); `tests/test_config_production.py` |
| Límite de peticiones por cliente: `RATE_LIMIT_PER_MINUTE` (30 por omisión) en ventana móvil de 60 s, `429` con `Retry-After` (ADR 0011) | Abuso o cliente defectuoso que agota recursos; un cliente no bloquea a otro | `app/rate_limiter.py` (`RateLimiter.check_rate_limit`); `app/main.py` (`_add_auth_middleware`) | `tests/test_rate_limiter.py` (reloj inyectado); `tests/test_production_endpoints.py` (`TestRateLimitingEndpoints`, `TestMultipleClientsRateLimit`); escenarios de `production.feature` |
| Tablero público sin datos y `/metrics` protegido: `/dashboard` responde `200` sin clave y sin cifras; la persona escribe la clave, se guarda en `sessionStorage` y se manda en `X-API-Key` a `/metrics` | Que el tablero requiera una clave imposible de mandar desde la URL sin meter la clave ni cifras en la página | `app/main.py` (`PUBLIC_PATHS`, ruta `/dashboard`, ruta `/metrics`); `app/static/dashboard.html` (`refresh`, `clearFigures`) | `tests/test_dashboard.py` (lee de `sessionStorage`, manda `X-API-Key`, consulta cada 5000 ms); escenario de `production_ready.feature` (`/dashboard` sin clave `200` y sin la clave; `/metrics` `401` sin clave y `200` con ella); `verification/contract/test_contract_05.py` (`test_dashboard_is_public_and_carries_no_key`, `test_metrics_still_need_a_key`) |
| Log sin valores de PII: `pii_detected` lleva `pii_type`, `count` y `direction`; `output_rejected` lleva solo el motivo; los errores registran el tipo, no el mensaje | Que datos personales o respuestas rechazadas queden en el log | `app/main.py` (`_log_pii`, `_safe_answer`, `_log_agent_run`, middleware `observe_request`); `app/pii.py` | `tests/test_pii_logging.py` (con el modelo caído, ni el correo ni el RFC aparecen en el log ni en la respuesta); `verification/contract/test_contract_05.py::test_pii_in_the_question_never_reaches_the_log` (corre con varios workers); pasos de `production_ready.feature` |

## Limitaciones honestas

- **Sin `API_KEYS` la API queda abierta fuera de producción (ADR 0010).** Si la variable está
  vacía y `ENVIRONMENT` no es `production`, el middleware no pide clave y `POST /ask` y
  `GET /metrics` quedan abiertos. Solo `ENVIRONMENT=production` lo impide, porque con `API_KEYS`
  vacía el arranque falla. Quien despliegue fuera de producción en una red no confiable debe
  configurar `API_KEYS`.
- `/dashboard` es público por diseño, pero no lleva cifras ni claves. Las cifras salen de
  `/metrics`, que sí exige la clave.
- El límite de peticiones, la caché y las métricas son por proceso y en memoria (ADR 0011 y 0005):
  con varios workers cada uno cuenta por separado y el límite efectivo por cliente puede ser mayor
  que `RATE_LIMIT_PER_MINUTE`. El tablero, al leer `/metrics` cada 5 s, también consume ese límite.
- El enmascarado usa expresiones regulares: cubre los seis formatos de la especificación, no
  nombres propios ni otros datos personales. No hay una prueba que mida falsos negativos más allá
  de los ejemplos de `tests/test_pii.py`.
- `pii_by_type` suma las detecciones de la pregunta y el historial (`record_pii(input_pii)`); las de
  la respuesta se registran en el log como `pii_detected` con `direction=output`, pero no entran a
  ese contador.
- El evento `audit` registra los argumentos de cada herramienta (`args`) sin pasarlos por
  `mask_pii`. Hoy llegan de un modelo que solo vio texto enmascarado; no hay una prueba que lo
  garantice.
- La clave la escribe la persona en el navegador y vive en `sessionStorage` mientras dure la sesión.

## Pendiente

El ADR 0016 (tablero) sigue pendiente; este documento no lo sustituye.
