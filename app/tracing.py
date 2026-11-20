"""Trazas opcionales en LangSmith, apagadas y ocultas por omisión (ADR 0006).

La clave ``LANGSMITH_API_KEY`` la lee ``langsmith`` del entorno; este módulo nunca
la recibe ni la escribe.
"""

from collections.abc import Iterator
from contextlib import contextmanager

import langsmith
from langsmith import traceable

from app.config import Settings

__all__ = ["Tracing", "traceable"]


class Tracing:
    """Abre el contexto de trazas de cada petición.

    :param settings: Configuración con ``tracing_enabled`` y ``hide_*``
    :type settings: Settings
    """

    def __init__(self, settings: Settings):
        self.enabled = settings.tracing_enabled
        self._client = None
        if self.enabled:
            # Se busca ``Client`` en el módulo al crear, no al importar.
            self._client = langsmith.Client(
                hide_inputs=settings.hide_inputs,
                hide_outputs=settings.hide_outputs,
            )

    @contextmanager
    def context(
        self,
        request_id: str,
        client: str | None = None,
        route: str | None = None,
        model: str | None = None,
    ) -> Iterator[dict]:
        """Contexto de trazas de una petición.

        Apagado, fija ``enabled=False`` para no depender de variables del entorno.
        Encendido, usa el cliente único y pone ``request_id``, ``client``,
        ``route`` y ``model`` en los metadatos (nunca la clave ni el texto de la
        conversación). Devuelve el diccionario de metadatos para que quien llama
        agregue ``cost_usd`` al terminar la corrida, cuando ya se conoce.

        :param request_id: Id de la petición
        :type request_id: str
        :param client: Nombre del cliente autenticado (opcional)
        :type client: str | None
        :param route: Motivo de la ruta de modelo elegida (opcional)
        :type route: str | None
        :param model: Modelo elegido (opcional)
        :type model: str | None
        :return: Los metadatos de la traza (vacíos si las trazas están apagadas)
        :rtype: Iterator[dict]
        """
        if not self.enabled:
            with langsmith.tracing_context(enabled=False):
                yield {}
            return
        metadata = {
            "request_id": request_id,
            "client": client or "anonymous",
            "route": route or "unknown",
            "model": model or "unknown",
        }
        with langsmith.tracing_context(
            enabled=True, client=self._client, metadata=metadata
        ):
            yield metadata
