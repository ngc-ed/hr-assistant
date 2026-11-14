"""Reloj inyectable: el único punto del producto que lee la hora del sistema."""

import time
from datetime import datetime, timezone
from typing import Protocol


class Clock(Protocol):
    """Protocolo de reloj que usan el log y el middleware."""

    def now(self) -> datetime:
        """Devuelve la hora actual con zona.

        :return: La hora actual en UTC
        :rtype: datetime
        """

    def monotonic(self) -> float:
        """Devuelve un contador que solo avanza, para medir duraciones.

        :return: Segundos del contador
        :rtype: float
        """


class SystemClock:
    """Reloj real del sistema operativo."""

    def now(self) -> datetime:
        """Devuelve la hora actual del sistema en UTC.

        :return: La hora actual con zona UTC
        :rtype: datetime
        """
        return datetime.now(timezone.utc)

    def monotonic(self) -> float:
        """Devuelve el contador monotónico de alta resolución del sistema.

        Se usa ``perf_counter`` porque ``time.monotonic`` en Windows avanza en
        saltos de unos 15 ms y daría latencias de cero.

        :return: Segundos del contador
        :rtype: float
        """
        return time.perf_counter()
