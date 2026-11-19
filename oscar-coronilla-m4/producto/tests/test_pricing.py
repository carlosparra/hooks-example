"""Pruebas de ``app.pricing``: costo en USD con la tabla de precios por millón."""

import io
import json
from pathlib import Path

import pytest

from app.main import create_app
from app.pricing import PriceTable

SMALL_MODEL = "@cf/meta/llama-3.1-8b-instruct-fast"
LARGE_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
PRODUCT_DIR = Path(__file__).resolve().parents[1]


def test_cost_follows_the_price_per_million_tokens(prices_file):
    prices = PriceTable.from_file(prices_file)

    # 1 M de entrada a 0.045 + 0.5 M de salida a 0.384.
    assert prices.cost(SMALL_MODEL, 1_000_000, 500_000) == pytest.approx(0.237)
    # Sin redondeo: decenas de tokens dan millonesimas de dolar.
    assert prices.cost(LARGE_MODEL, 10, 2) == pytest.approx(7.436e-06)
    assert prices.cost(LARGE_MODEL, 0, 0) == 0


def test_application_does_not_start_when_a_model_has_no_price(
    tmp_path, make_cost_settings, directory
):
    incomplete = tmp_path / "incomplete_prices.json"
    incomplete.write_text(
        json.dumps({"models": {LARGE_MODEL: {"input": 0.293, "output": 2.253}}}),
        encoding="utf-8",
    )

    with pytest.raises((ValueError, KeyError), match="llama-3.1-8b"):
        create_app(
            settings=make_cost_settings(prices_path=incomplete),
            directory=directory,
            log_stream=io.StringIO(),
        )


def test_product_price_table_has_currency_unit_and_prices_per_model():
    # Solo lee dentro de product/: valida la estructura, no la compara con spec/.
    product_prices = PRODUCT_DIR / "data" / "model_prices.json"
    table = json.loads(product_prices.read_text(encoding="utf-8"))

    assert table["currency"] == "USD"
    assert table["unit"] == "per million tokens"
    models = table["models"]
    assert {SMALL_MODEL, LARGE_MODEL} <= set(models)
    for name, price in models.items():
        for kind in ("input", "output"):
            value = price[kind]
            assert isinstance(value, (int, float)), f"{name}.{kind} no es numerico"
            assert value >= 0, f"{name}.{kind} es negativo"
