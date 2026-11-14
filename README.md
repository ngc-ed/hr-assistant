# HR Assistant

Asistente de Recursos Humanos: una API web sin estado (FastAPI) con un agente que
responde preguntas sobre el directorio de empleados usando dos herramientas de solo
lectura (`get_employee` y `search_by_department`). Incluye una página web sencilla.

Cada petición se puede rastrear: lleva un `request_id`, deja un log JSON por evento
en la salida estándar y suma a las métricas del proceso. Opcionalmente, el agente
manda trazas a LangSmith.

Cada respuesta dice qué modelo usó, por qué y cuánto costó. Con
`MODEL_PROVIDER=gateway` usa modelos reales de Cloudflare Workers AI a través de AI
Gateway; con `fake` (por omisión) usa dos modelos simulados que se llaman como
`MODEL_SMALL` y `MODEL_LARGE` y cuestan lo mismo que ellos, sin red ni cuota.

La arquitectura está en `doc/architecture.md` y las decisiones en `doc/adr/`.

## Cómo correrlo

Desde la carpeta `product/`:

```bash
uv pip install -r requirements.txt
uv run uvicorn app.main:app --port 8000
```

Luego abre `http://127.0.0.1:8000/` en el navegador.

## Rutas

| Método y ruta | Qué hace |
| --- | --- |
| `GET /` | La página web; bajo cada respuesta muestra el id de la petición |
| `GET /health` | `{"status": "ok", "pid": ...}` |
| `POST /ask` (pide `X-API-Key`) | Recibe `{"question", "history"}`; responde `answer`, `steps`, `tools_used`, `input_tokens`, `output_tokens`, `request_id`, `model`, `route`, `cached_calls` y `cost_usd` |
| `GET /metrics` (pide `X-API-Key`) | `pid`, `requests`, `error_rate`, `latency_ms` (`p50`, `p95`), `tokens` (`input`, `output`), `slo` (`p95_ms_target`, `met`) y `cost_usd` acumulado |

Toda respuesta trae el encabezado `X-Request-ID`. Si el cliente lo manda con forma
válida (`[A-Za-z0-9._:-]`, de 1 a 128 caracteres) se conserva; si no, se genera un
UUID. Un error inesperado responde `500` con
`{"detail": "internal error", "request_id": ...}`. Si el modelo falla (gateway
caído, tiempo agotado o respuesta inválida) responde `502` con
`{"detail": "model unavailable", "request_id": ...}`.

## Acceso por clave y límite de peticiones

`POST /ask` y `GET /metrics` exigen el encabezado `X-API-Key`. `GET /`, `GET /health`
y `/docs` no piden clave. Cada cliente tiene su clave en `API_KEYS`, con la forma
`cliente:clave,cliente2:clave2`.

- Sin clave o con una inválida responde `401` con
  `{"detail": "invalid or missing API key"}`.
- Más de `RATE_LIMIT_PER_MINUTE` peticiones de un cliente en un minuto responde
  `429` con `{"detail": "rate limit exceeded"}` y el encabezado `Retry-After`
  (segundos que faltan).
- Si `API_KEYS` está mal formada, el producto no arranca; el error dice qué entrada
  falla y su largo, nunca su valor.
- Con `ENVIRONMENT=production` el producto se niega a arrancar si el modelo es
  `fake`, si `API_KEYS` está vacía o tiene una clave de menos de 16 caracteres, o si
  hay trazas con `HIDE_INPUTS` o `HIDE_OUTPUTS` distintos de `true`. Las reglas están
  en `doc/compliance-checklist.md`.

La clave nunca se escribe en el log, en la traza ni en un mensaje de error.

## La página web y la clave

La página tiene un campo de clave (`data-testid="api-key"`, tipo contraseña). La
clave se guarda en `sessionStorage` (nunca en `localStorage` ni en el código de la
página) y se manda en `X-API-Key`. Con `401` muestra «Clave inválida»; con `429`,
«Demasiadas preguntas; espera N segundos».

## Prueba de humo

Contra un producto ya publicado o corriendo:

```bash
SMOKE_API_KEY=<tu-clave> uv run python scripts/smoke.py <url>
```

La clave se lee solo de la variable de entorno `SMOKE_API_KEY`, nunca de un
argumento. Comprueba `/health` (200), `/ask` sin clave (401) y `/ask` con clave
(200), e imprime `[OK]` o `[FAIL]` en cada una.

## Contenedor

```bash
docker build -t hr-assistant .
docker run --env-file .env -p 8000:8000 hr-assistant
```

La imagen usa `python:3.12-slim`, corre con un usuario que no es root y escucha en
`PORT` si existe (8000 si no). El `.env` no entra a la imagen: se pasa con
`--env-file`.

## Pipeline de CI

`.github/workflows/ci.yml` corre en cada push y pull request con cuatro trabajos
encadenados: `style`, `unit`, `e2e` y `docker`. Cada etapa se ve en la pestaña
Actions de GitHub.

## Palancas de costo

1. **Enrutamiento** (`route`): una regla en código elige el modelo. Va a
   `MODEL_LARGE` si `ROUTING=false` (`routing_disabled`), si la pregunta pasa de
   `ROUTER_MAX_CHARS` caracteres (`long_question`) o si contiene «compara»,
   «resume», «explica», «por qué», «analiza» o «todos» (`keyword:<palabra>`). Si
   no, va a `MODEL_SMALL` (`simple`).
2. **Ventana de historial**: al modelo solo llegan los últimos `HISTORY_WINDOW`
   mensajes del historial.
3. **Tope de salida**: `MODEL_MAX_TOKENS` en cada llamada.
4. **Caché de AI Gateway**: con `CACHE_TTL_SECONDS` mayor que 0 se manda
   `cf-aig-cache-ttl`; si el gateway responde `cf-aig-cache-status: HIT`, la llamada
   cuenta en `cached_calls` y no cuesta.

`cost_usd` se calcula con los tokens de las llamadas no cacheadas y los precios de
`data/model_prices.json` (USD por millón de tokens, copia de
`spec/model_prices.json`). Los precios cambian: revisa el campo `checked` y la
página de precios de Cloudflare antes de usarlos. Si un modelo configurado no tiene
precio, el producto no arranca.

## Usar el modelo real (AI Gateway)

1. Copia `.env.example` como `.env` y pon `MODEL_PROVIDER=gateway`.
2. Llena `CF_ACCOUNT_ID`, `CF_GATEWAY_ID` y `CF_API_TOKEN` con los datos de tu
   cuenta de Cloudflare. El token es secreto: nunca lo subas al repositorio.
3. Arranca cargando el archivo, desde la carpeta `product/`:

   ```bash
   uv run --env-file .env uvicorn app.main:app --port 8000
   ```

   El producto no lee `.env` por su cuenta: solo ve las variables del entorno del
   proceso. Sin `--env-file .env` (o sin exportar antes las variables en la
   terminal), las variables `CF_*` y `MODEL_PROVIDER=gateway` se ignoran y el
   producto arranca con el modelo simulado. Si falta alguna de las tres variables,
   el producto no arranca y el mensaje nombra la variable (nunca su valor).

Las llamadas van a
`https://gateway.ai.cloudflare.com/v1/{CF_ACCOUNT_ID}/{CF_GATEWAY_ID}/workers-ai/v1/chat/completions`
con un tiempo de espera de 30 segundos.

## Log

Una línea JSON por evento con `ts` (UTC), `service`, `event` y `request_id`:

- `request`: `method`, `path`, `status`, `latency_ms`.
- `client`: `agent_run`, `audit` y `error` llevan el nombre del cliente
  autenticado (nunca su clave).
- `agent_run`: `question_chars`, `history_messages`, `history_sent`, `steps`,
  `tools`, `input_tokens`, `output_tokens`, `stopped`, `model`, `route`,
  `cached_calls`, `cost_usd`. Nunca el texto de la pregunta ni de la respuesta.
- `audit`: `action: "tool_call"`, `tool`, `args`, uno por herramienta ejecutada.
- `error`: `error_type` (solo el tipo, sin el mensaje).

Para seguir una petición, filtra el log por su `request_id`.

## Variables de entorno

| Variable | Por omisión | Para qué |
| --- | --- | --- |
| `MODEL_PROVIDER` | `fake` | Qué modelo usar: `fake` o `gateway` |
| `AGENT_MAX_STEPS` | `3` | Tope de vueltas del bucle del agente |
| `MAX_QUESTION_CHARS` | `2000` | Largo máximo de la pregunta |
| `EMPLOYEES_PATH` | `data/employees.json` | Archivo de empleados (relativo a `product/`) |
| `SERVICE_NAME` | `hr-assistant` | Campo `service` del log |
| `SLO_P95_MS` | `2000` | Meta de latencia p95 en milisegundos |
| `LANGSMITH_TRACING` | `false` | Enciende las trazas en LangSmith (`true`/`false`) |
| `LANGSMITH_API_KEY` | sin valor | Clave de LangSmith; sin ella no hay trazas |
| `HIDE_INPUTS` | `true` | No mandar a LangSmith las entradas |
| `HIDE_OUTPUTS` | `true` | No mandar a LangSmith las salidas |
| `CF_ACCOUNT_ID` | vacía | Cuenta de Cloudflare (obligatoria con `gateway`) |
| `CF_GATEWAY_ID` | `default` | Id del AI Gateway (no puede quedar vacía con `gateway`) |
| `CF_API_TOKEN` | vacía | Token de Cloudflare, secreto (obligatorio con `gateway`) |
| `MODEL_SMALL` | `@cf/meta/llama-3.1-8b-instruct-fast` | Modelo barato |
| `MODEL_LARGE` | `@cf/meta/llama-3.3-70b-instruct-fp8-fast` | Modelo capaz |
| `ROUTING` | `true` | Enrutamiento por pregunta (`true`/`false`) |
| `ROUTER_MAX_CHARS` | `80` | Preguntas más largas van al modelo capaz |
| `HISTORY_WINDOW` | `6` | Mensajes de historial que se mandan (entero `>= 0`) |
| `MODEL_MAX_TOKENS` | `300` | Tope de tokens de salida |
| `MODEL_TEMPERATURE` | `0` | Temperatura; con 0 las evaluaciones son repetibles |
| `CACHE_TTL_SECONDS` | `0` | Caché del gateway en segundos (0: apagada) |
| `PRICES_PATH` | `data/model_prices.json` | Precios por modelo (relativo a `product/`) |
| `ENVIRONMENT` | `development` | Ambiente: `development` o `production`; compliance estricta en `production` |
| `API_KEYS` | vacía | Clientes y claves en formato `cliente:clave,cliente2:clave2` (secreto) |
| `RATE_LIMIT_PER_MINUTE` | `30` | Límite de peticiones por cliente por minuto |

Todas las variables están en `.env.example`, sin valores secretos.

Las trazas solo se encienden con `LANGSMITH_TRACING=true` y la clave presente. La
clave se lee del entorno (por ejemplo, de un `.env` que no se sube al repositorio y
se carga con `uv run --env-file .env ...`); nunca se escribe en el código, en la configuración ni en el log. Un valor inválido
(por ejemplo `SLO_P95_MS=0` o `LANGSMITH_TRACING=quizas`) impide arrancar.

## Cómo probarlo

Desde la raíz del repositorio:

```bash
uv run python -m verification unit      # pruebas del producto con cobertura
uv run python -m verification contract  # contrato por HTTP
uv run python -m verification qa        # estilo de QA.md
uv run python -m verification e2e       # pruebas de Playwright de la página
uv run python -m verification evaluate  # calidad y costo: línea base contra palancas
```

Antes de `e2e`, instala el navegador una vez con `uv run playwright install chromium`.
`evaluate` corre el set de evaluación con el modelo simulado dos veces (sin
enrutamiento ni ventana, y con la configuración por omisión) y pasa solo si la
calidad no baja y el costo sí baja.

Las pruebas no usan red: inyectan un reloj fijo, un log en memoria, modelos de guion
y, para el gateway, un cliente HTTP con `httpx.MockTransport`.
