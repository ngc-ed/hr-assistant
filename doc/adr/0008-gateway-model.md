# 0008. Modelo real por Cloudflare AI Gateway con cliente HTTP inyectado

Estado: propuesto

## Contexto

Se agrega el modelo real (Workers AI a través de AI Gateway) sin romper ADR 0002, sin
red en las pruebas y sin exponer el token de Cloudflare.

## Decisión

`app/gateway.py` implementa `LanguageModel` con `GatewayModel(name, settings,
client)`, donde `client` es un `httpx.Client` inyectado (en pruebas, con
`httpx.MockTransport`) con tiempo de espera fijo. Llama a
`.../workers-ai/v1/chat/completions` con `Bearer`, `max_tokens` y `temperature`;
antepone un mensaje `system` con el protocolo JSON de herramientas; manda
`cf-aig-cache-ttl` si `CACHE_TTL_SECONDS > 0` y marca la llamada como cacheada
(`Completion.cached`) si recibe `cf-aig-cache-status: HIT`. Cualquier fallo (red,
tiempo, estado no 2xx, cuerpo inesperado) lanza `ModelUnavailableError` con mensaje
fijo y sin encadenar la excepción original; la API la traduce a
`502 {"detail": "model unavailable", "request_id"}`. Con `gateway`, `CF_ACCOUNT_ID` o
`CF_API_TOKEN` vacías, o `CF_GATEWAY_ID` presente pero vacía (su valor por omisión es
`default`), impiden arrancar con `ConfigError`. El token vive en `Settings` con
`repr=False` y nunca se escribe en logs, errores ni trazas.

## Consecuencias

- Amplía ADR 0002: el agente sigue sin conocer al proveedor.
- El mensaje `system` solo lo agrega el modelo real; el simulado no cambia.
- El cliente distingue "el modelo no está" (502) de un error nuestro (500).
- La caché del gateway es opcional (TTL 0 por omisión) y no guarda estado en la API
  (ADR 0001 se mantiene).
