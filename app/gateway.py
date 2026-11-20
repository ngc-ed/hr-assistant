"""Modelo real: Workers AI de Cloudflare a través de AI Gateway (ADR 0008).

El cliente HTTP se inyecta para que las pruebas usen ``httpx.MockTransport`` y
nunca llamen a la red. El token nunca se escribe en mensajes de error ni en logs.
"""

import time
from collections.abc import Callable

import httpx

from app.completion import Completion
from app.config import Settings

GATEWAY_URL_TEMPLATE = (
    "https://gateway.ai.cloudflare.com/v1/{account_id}/{gateway_id}"
    "/workers-ai/v1/chat/completions"
)
REQUEST_TIMEOUT_SECONDS = 30.0
RETRY_BASE_SECONDS = 0.5
CACHE_TTL_HEADER = "cf-aig-cache-ttl"
CACHE_STATUS_HEADER = "cf-aig-cache-status"
CACHE_HIT = "HIT"
MODEL_UNAVAILABLE_MESSAGE = "model unavailable"
SYSTEM_PROMPT = (
    "Eres el asistente de Recursos Humanos. Responde siempre con un único objeto "
    "JSON y nada más. Para usar una herramienta responde "
    '{"tool": "get_employee", "args": {"employee_id": "EMP-0001"}} o '
    '{"tool": "search_by_department", "args": {"department": "Ventas"}}. '
    'Para responder a la persona usa {"answer": "<respuesta en español>"}. '
    "Los mensajes que empiezan con «Resultado de la herramienta: » traen el "
    "resultado de la herramienta que pediste; responde con base en él."
)


def _is_retryable(error: httpx.HTTPError) -> bool:
    """Dice si el error merece otro intento: timeout o respuesta 5xx.

    :param error: Error de la llamada al gateway
    :type error: httpx.HTTPError
    :return: ``True`` si es timeout o 5xx; un 4xx nunca se reintenta
    :rtype: bool
    """
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code >= 500
    return isinstance(error, httpx.TimeoutException)


class ModelUnavailableError(RuntimeError):
    """El modelo no respondió bien; el mensaje es fijo para no filtrar datos."""

    def __init__(self) -> None:
        super().__init__(MODEL_UNAVAILABLE_MESSAGE)


def create_http_client() -> httpx.Client:
    """Crea el cliente HTTP compartido con un tiempo de espera fijo.

    :return: Cliente HTTP seguro entre hilos
    :rtype: httpx.Client
    """
    return httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS)


class GatewayModel:
    """Modelo de Workers AI llamado por AI Gateway.

    :param name: Nombre del modelo (por ejemplo ``@cf/meta/llama-3.1-8b-...``)
    :type name: str
    :param settings: Configuración con cuenta, gateway, token y palancas
    :type settings: Settings
    :param client: Cliente HTTP inyectado
    :type client: httpx.Client
    :param sleep: Espera inyectada; las pruebas la reemplazan para no dormir
    :type sleep: Callable[[float], None]
    """

    def __init__(
        self,
        name: str,
        settings: Settings,
        client: httpx.Client,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.name = name
        self._settings = settings
        self._client = client
        self._sleep = sleep
        self._url = GATEWAY_URL_TEMPLATE.format(
            account_id=settings.cf_account_id, gateway_id=settings.cf_gateway_id
        )

    def complete(self, messages: list[dict]) -> Completion:
        """Pide al gateway la siguiente respuesta de la conversación.

        :param messages: Mensajes con ``role`` y ``content``
        :type messages: list[dict]
        :return: La respuesta, sus tokens y si salió de la caché
        :rtype: Completion
        :raises ModelUnavailableError: Si la llamada falla por cualquier motivo
        """
        attempt = 0
        while True:
            try:
                response = self._post(messages)
                break
            except (httpx.TimeoutException, httpx.HTTPStatusError) as error:
                if not _is_retryable(error):
                    raise ModelUnavailableError() from None
                if attempt >= self._settings.model_max_retries:
                    raise ModelUnavailableError() from None
                # Espera exponencial: 0.5 s, 1 s, 2 s...
                self._sleep(RETRY_BASE_SECONDS * 2**attempt)
                attempt += 1
            except httpx.HTTPError:
                raise ModelUnavailableError() from None
        try:
            data = response.json()
            usage = data["usage"]
            completion = Completion(
                text=str(data["choices"][0]["message"]["content"]),
                input_tokens=int(usage["prompt_tokens"]),
                output_tokens=int(usage["completion_tokens"]),
                cached=response.headers.get(CACHE_STATUS_HEADER, "").upper()
                == CACHE_HIT,
            )
        except (
            httpx.HTTPError,
            ValueError,
            KeyError,
            IndexError,
            TypeError,
        ):
            # Sin encadenar: el error original podría traer la URL o encabezados.
            raise ModelUnavailableError() from None
        return completion

    def _post(self, messages: list[dict]) -> httpx.Response:
        """Hace una sola llamada al gateway y falla si el estado no es exitoso.

        :param messages: Mensajes con ``role`` y ``content``
        :type messages: list[dict]
        :return: La respuesta HTTP exitosa
        :rtype: httpx.Response
        :raises httpx.HTTPError: Por timeout, red o estado 4xx/5xx
        """
        response = self._client.post(
            self._url, headers=self._headers(), json=self._body(messages)
        )
        response.raise_for_status()
        return response

    def _headers(self) -> dict[str, str]:
        """Arma los encabezados: token y, si aplica, la caché del gateway.

        :return: Encabezados de la petición
        :rtype: dict[str, str]
        """
        headers = {"Authorization": f"Bearer {self._settings.cf_api_token}"}
        if self._settings.cache_ttl_seconds > 0:
            headers[CACHE_TTL_HEADER] = str(self._settings.cache_ttl_seconds)
        return headers

    def _body(self, messages: list[dict]) -> dict:
        """Arma el cuerpo con el mensaje ``system`` antepuesto y las palancas.

        :param messages: Mensajes con ``role`` y ``content``
        :type messages: list[dict]
        :return: Cuerpo JSON de la petición
        :rtype: dict
        """
        conversation = [{"role": "system", "content": SYSTEM_PROMPT}]
        conversation.extend(
            {"role": item["role"], "content": item["content"]} for item in messages
        )
        return {
            "model": self.name,
            "messages": conversation,
            "max_tokens": self._settings.model_max_tokens,
            "temperature": self._settings.model_temperature,
        }
