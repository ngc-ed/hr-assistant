"""Log estructurado: una línea JSON por evento (ADR 0004)."""

import json
import sys
from typing import Any, TextIO

from app.clock import Clock


class JsonLogger:
    """Escribe eventos como líneas JSON con los campos comunes.

    :param service: Nombre del servicio (campo ``service``)
    :type service: str
    :param clock: Reloj del que sale el campo ``ts``
    :type clock: Clock
    :param stream: Flujo de salida; si es ``None`` se usa ``sys.stdout`` al escribir
    :type stream: TextIO | None
    """

    def __init__(self, service: str, clock: Clock, stream: TextIO | None = None):
        self._service = service
        self._clock = clock
        self._stream = stream

    def log(self, event: str, request_id: str, client: str | None = None,
            **fields: Any) -> None:
        """Escribe un evento como una sola línea JSON y vacía el búfer.

        :param event: Nombre del evento (``request``, ``agent_run``, ...)
        :type event: str
        :param request_id: Id de la petición a la que pertenece el evento
        :type request_id: str
        :param client: Nombre del cliente (opcional, por auditoría)
        :type client: str | None
        :param fields: Campos propios del evento
        :type fields: Any
        """
        record = {
            "ts": self._clock.now().isoformat(timespec="milliseconds"),
            "service": self._service,
            "event": event,
            "request_id": request_id,
            **fields,
        }
        # Agregar cliente si se proporciona
        if client:
            record["client"] = client
        # Se resuelve stdout al escribir para respetar capturas y redirecciones.
        stream = self._stream if self._stream is not None else sys.stdout
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        stream.flush()
