"""Costo en USD de cada respuesta con una tabla de precios local (ADR 0009).

Los precios están en USD por millón de tokens. El costo no se redondea: con
decenas de tokens resulta en millonésimas de dólar.
"""

import json
from pathlib import Path
from typing import Iterable, Mapping

TOKENS_PER_PRICE_UNIT = 1_000_000


class PriceTable:
    """Precios de entrada y salida por modelo.

    :param prices: Por nombre de modelo, ``{"input": ..., "output": ...}``
    :type prices: Mapping[str, Mapping[str, float]]
    :raises ValueError: Si algún precio falta, no es número o es negativo
    """

    def __init__(self, prices: Mapping[str, Mapping[str, float]]) -> None:
        self._prices: dict[str, tuple[float, float]] = {}
        for model, price in prices.items():
            try:
                pair = (float(price["input"]), float(price["output"]))
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(f"invalid price for model {model!r}") from error
            if min(pair) < 0:
                raise ValueError(f"negative price for model {model!r}")
            self._prices[model] = pair

    @classmethod
    def from_file(cls, path: str | Path) -> "PriceTable":
        """Lee la tabla de un archivo JSON con la llave ``models``.

        :param path: Ruta del archivo de precios
        :type path: str | pathlib.Path
        :return: Tabla de precios
        :rtype: PriceTable
        :raises FileNotFoundError: Si el archivo no existe
        :raises ValueError: Si el archivo no tiene la forma esperada
        """
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        models = data.get("models") if isinstance(data, dict) else None
        if not isinstance(models, dict):
            raise ValueError("price file must have a 'models' object")
        return cls(models)

    def require(self, models: Iterable[str]) -> None:
        """Verifica que cada modelo tenga precio; se usa al arrancar.

        :param models: Nombres de modelo que la aplicación va a usar
        :type models: Iterable[str]
        :raises ValueError: Si algún modelo no tiene precio
        """
        missing = [model for model in models if model not in self._prices]
        if missing:
            raise ValueError(f"no price for models: {', '.join(missing)}")

    def cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calcula el costo en USD de unos tokens con el precio del modelo.

        :param model: Nombre del modelo
        :type model: str
        :param input_tokens: Tokens de entrada facturables
        :type input_tokens: int
        :param output_tokens: Tokens de salida facturables
        :type output_tokens: int
        :return: Costo en USD, sin redondear
        :rtype: float
        :raises ValueError: Si el modelo no tiene precio
        """
        self.require([model])
        input_price, output_price = self._prices[model]
        return (
            input_tokens * input_price + output_tokens * output_price
        ) / TOKENS_PER_PRICE_UNIT
