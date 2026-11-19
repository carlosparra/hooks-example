"""Tipos comunes a todos los modelos: la respuesta y el error de disponibilidad.

Viven aparte para que ``app.llm`` y ``app.gateway`` los compartan sin importarse
entre sí; ``app.llm`` los vuelve a exportar.
"""

from dataclasses import dataclass
from typing import Mapping

Message = Mapping[str, str]


class ModelUnavailableError(Exception):
    """El modelo real no respondió o su respuesta no se pudo leer.

    El mensaje nunca lleva el token ni el cuerpo de la respuesta del proveedor.
    """


@dataclass(frozen=True)
class ModelReply:
    """Respuesta de un modelo: texto JSON y tokens usados.

    :param text: Texto devuelto por el modelo (un objeto JSON)
    :type text: str
    :param input_tokens: Tokens de entrada
    :type input_tokens: int
    :param output_tokens: Tokens de salida
    :type output_tokens: int
    :param cached: Si la respuesta salió de la caché del gateway (no cuesta)
    :type cached: bool
    """

    text: str
    input_tokens: int
    output_tokens: int
    cached: bool = False
