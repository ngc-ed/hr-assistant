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
    def context(self, request_id: str, client: str | None = None) -> Iterator[None]:
        """Contexto de trazas de una petición.

        Apagado, fija ``enabled=False`` para no depender de variables del entorno.
        Encendido, usa el cliente único y pone el ``request_id`` y, si hay, el
        nombre del cliente en los metadatos (nunca su clave).

        :param request_id: Id de la petición
        :type request_id: str
        :param client: Nombre del cliente autenticado (opcional)
        :type client: str | None
        :return: Un contexto sin valor
        :rtype: Iterator[None]
        """
        if not self.enabled:
            with langsmith.tracing_context(enabled=False):
                yield
            return
        metadata = {"request_id": request_id}
        if client:
            metadata["client"] = client
        with langsmith.tracing_context(
            enabled=True, client=self._client, metadata=metadata
        ):
            yield
