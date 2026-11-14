"""Límite de peticiones por cliente por minuto (ventana móvil)."""

import math

from fastapi import HTTPException

from app.clock import Clock, SystemClock


class RateLimiter:
    """Limita peticiones por cliente en ventanas móviles de 60 segundos.

    Usa ``clock.monotonic()`` para medir duraciones sin ser afectado
    por cambios del reloj del sistema.

    :param requests_per_minute: Límite de peticiones por cliente por minuto
    :type requests_per_minute: int
    :param clock: Reloj inyectado; si falta se usa el del sistema
    :type clock: Clock | None
    """

    WINDOW_SECONDS = 60

    def __init__(self, requests_per_minute: int, clock: Clock | None = None):
        """Inicializa el rate limiter.

        :param requests_per_minute: Máximo de peticiones por minuto
        :type requests_per_minute: int
        :param clock: Reloj inyectado (por omisión: SystemClock)
        :type clock: Clock | None
        """
        self.requests_per_minute = requests_per_minute
        self.clock = clock or SystemClock()
        # {cliente: [(tiempo_monotónico, _), ...]}
        self._requests: dict[str, list[float]] = {}

    def check_rate_limit(self, client: str) -> None:
        """Verifica si el cliente pasó el límite en la ventana móvil.

        :param client: Nombre del cliente
        :type client: str
        :raises HTTPException: 429 si se excede el límite con Retry-After
        """
        now = self.clock.monotonic()
        window_start = now - self.WINDOW_SECONDS

        # Limpiar peticiones fuera de la ventana (window_start, now)
        # Ventana móvil: (t-60, t) - abierta en el límite izquierdo
        if client in self._requests:
            self._requests[client] = [
                req_time for req_time in self._requests[client]
                if req_time > window_start
            ]

        if client not in self._requests:
            self._requests[client] = []

        # Comprobar límite
        if len(self._requests[client]) >= self.requests_per_minute:
            # Si hay peticiones registradas, calcular retry_after basado en la más vieja
            if self._requests[client]:
                oldest_request = self._requests[client][0]
                seconds_remaining = oldest_request + self.WINDOW_SECONDS - now
                retry_after = max(1, math.ceil(seconds_remaining))
            else:
                # Si no hay peticiones (ej. límite=0), usar 60 segundos
                retry_after = self.WINDOW_SECONDS

            raise HTTPException(
                status_code=429,
                detail="rate limit exceeded",
                headers={"Retry-After": str(retry_after)},
            )

        # Registrar la petición
        self._requests[client].append(now)
