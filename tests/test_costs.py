"""Pruebas unitarias de la tabla de precios y del costo por respuesta."""

import json

import pytest

from app.config import ConfigError
from app.costs import PriceTable

SMALL = "@cf/meta/llama-3.1-8b-instruct-fast"
LARGE = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"


@pytest.fixture
def prices(tmp_path):
    """Tabla de precios leída de un archivo con el formato de la especificación."""
    path = tmp_path / "model_prices.json"
    data = {
        "currency": "USD",
        "unit": "per million tokens",
        "models": {SMALL: {"input": 0.045, "output": 0.384}},
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return PriceTable.from_file(path)


def test_cost_is_computed_in_usd_per_million_tokens(prices):
    assert prices.cost_usd(SMALL, 1_000_000, 0) == pytest.approx(0.045)
    assert prices.cost_usd(SMALL, 2000, 500) == pytest.approx(
        (2000 * 0.045 + 500 * 0.384) / 1_000_000
    )
    assert prices.cost_usd(SMALL, 0, 0) == 0


def test_model_without_price_raises_config_error(prices):
    with pytest.raises(ConfigError) as error:
        prices.price_of(LARGE)
    assert LARGE in str(error.value)


def test_require_fails_at_startup_when_a_configured_model_has_no_price(prices):
    prices.require([SMALL])
    with pytest.raises(ConfigError):
        prices.require([SMALL, LARGE])
