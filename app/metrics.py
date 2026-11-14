"""Métricas en memoria de este proceso (ADR 0005)."""

from collections import deque
from threading import Lock

DEFAULT_LATENCY_WINDOW = 1000
SERVER_ERROR_STATUS = 500


def _nearest_rank(sorted_values: list[float], percentile: int) -> float:
    """Calcula un percentil por el método de rango más cercano.

    :param sorted_values: Valores ordenados de menor a mayor (no vacío)
    :type sorted_values: list[float]
    :param percentile: Percentil entre 1 y 100
    :type percentile: int
    :return: El valor en el rango más cercano
    :rtype: float
    """
    count = len(sorted_values)
    # Techo de percentile * count / 100 con aritmética entera, sin redondeos.
    rank = -(-percentile * count // 100)
    return float(sorted_values[max(rank, 1) - 1])


class Metrics:  # pylint: disable=too-many-instance-attributes
    """Cuenta peticiones, errores, latencias, tokens y costo, seguro entre hilos.

    :param slo_p95_ms: Meta de latencia p95 en milisegundos
    :type slo_p95_ms: int
    :param window: Cuántas latencias recientes se usan para los percentiles
    :type window: int
    """

    def __init__(self, slo_p95_ms: int, window: int = DEFAULT_LATENCY_WINDOW):
        self._slo_p95_ms = slo_p95_ms
        self._latencies: deque[float] = deque(maxlen=window)
        self._requests = 0
        self._errors = 0
        self._input_tokens = 0
        self._output_tokens = 0
        self._cost_usd = 0.0
        self._lock = Lock()

    def record_request(self, status: int, latency_ms: float) -> None:
        """Registra una petición terminada.

        :param status: Código HTTP de la respuesta
        :type status: int
        :param latency_ms: Latencia en milisegundos
        :type latency_ms: float
        """
        with self._lock:
            self._requests += 1
            if status >= SERVER_ERROR_STATUS:
                self._errors += 1
            self._latencies.append(latency_ms)

    def record_tokens(self, input_tokens: int, output_tokens: int) -> None:
        """Suma los tokens de una corrida del agente.

        :param input_tokens: Tokens de entrada
        :type input_tokens: int
        :param output_tokens: Tokens de salida
        :type output_tokens: int
        """
        with self._lock:
            self._input_tokens += input_tokens
            self._output_tokens += output_tokens

    def record_cost(self, cost_usd: float) -> None:
        """Suma el costo de una respuesta.

        :param cost_usd: Costo en USD
        :type cost_usd: float
        """
        with self._lock:
            self._cost_usd += cost_usd

    def snapshot(self, pid: int) -> dict:
        """Devuelve el estado actual con la forma de ``GET /metrics``.

        :param pid: Id del proceso que reporta
        :type pid: int
        :return: Peticiones, tasa de error, latencias, tokens, SLO y costo
        :rtype: dict
        """
        with self._lock:
            latencies = sorted(self._latencies)
            requests = self._requests
            errors = self._errors
            tokens = {"input": self._input_tokens, "output": self._output_tokens}
            cost_usd = self._cost_usd
        p50 = _nearest_rank(latencies, 50) if latencies else 0.0
        p95 = _nearest_rank(latencies, 95) if latencies else 0.0
        return {
            "pid": pid,
            "requests": requests,
            "error_rate": errors / requests if requests else 0.0,
            "latency_ms": {"p50": p50, "p95": p95},
            "tokens": tokens,
            "slo": {"p95_ms_target": self._slo_p95_ms, "met": p95 < self._slo_p95_ms},
            "cost_usd": cost_usd,
        }
