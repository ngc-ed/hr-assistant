"""Tabla de precios por modelo y costo por respuesta (ADR 0009)."""

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from app.config import ConfigError

TOKENS_PER_PRICE_UNIT = 1_000_000


@dataclass(frozen=True)
class Price:
    """Precio de un modelo en USD por millón de tokens.

    :param input_usd: Precio de un millón de tokens de entrada
    :type input_usd: float
    :param output_usd: Precio de un millón de tokens de salida
    :type output_usd: float
    """

    input_usd: float
    output_usd: float


class PriceTable:
    """Precios por nombre de modelo.

    :param prices: Precio de cada modelo por nombre
    :type prices: Mapping[str, Price]
    """

    def __init__(self, prices: Mapping[str, Price]):
        self._prices = dict(prices)

    @classmethod
    def from_file(cls, path: str | Path) -> "PriceTable":
        """Lee la tabla de la clave ``models`` de un archivo JSON.

        :param path: Ruta del archivo de precios
        :type path: str | Path
        :return: La tabla de precios
        :rtype: PriceTable
        :raises ConfigError: Si el archivo no existe o no tiene el formato esperado
        """
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            prices = {
                name: Price(
                    input_usd=float(item["input"]), output_usd=float(item["output"])
                )
                for name, item in data["models"].items()
            }
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            raise ConfigError(f"PRICES_PATH {str(path)!r} is not valid") from error
        return cls(prices)

    def price_of(self, name: str) -> Price:
        """Devuelve el precio de un modelo.

        :param name: Nombre del modelo
        :type name: str
        :return: Su precio
        :rtype: Price
        :raises ConfigError: Si el modelo no tiene precio
        """
        price = self._prices.get(name)
        if price is None:
            raise ConfigError(f"model {name!r} has no price in PRICES_PATH")
        return price

    def require(self, names: Iterable[str]) -> None:
        """Comprueba al arrancar que cada modelo configurado tenga precio.

        :param names: Nombres de los modelos configurados
        :type names: Iterable[str]
        :raises ConfigError: Si alguno no tiene precio
        """
        for name in names:
            self.price_of(name)

    def cost_usd(self, name: str, input_tokens: int, output_tokens: int) -> float:
        """Calcula el costo en USD, sin redondear.

        :param name: Nombre del modelo
        :type name: str
        :param input_tokens: Tokens de entrada facturables
        :type input_tokens: int
        :param output_tokens: Tokens de salida facturables
        :type output_tokens: int
        :return: Costo en USD
        :rtype: float
        :raises ConfigError: Si el modelo no tiene precio
        """
        price = self.price_of(name)
        total = input_tokens * price.input_usd + output_tokens * price.output_usd
        return total / TOKENS_PER_PRICE_UNIT
