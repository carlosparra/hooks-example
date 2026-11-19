"""Detector local de información personal (PII) con expresiones regulares.

Sin red ni dependencias externas (ADR 0013). Las funciones públicas devuelven
solo los **tipos** encontrados, nunca los valores, para que quien las use no
pueda filtrar el dato al registrarlo.

Los patrones exigen su largo exacto y límites de palabra para no confundir
números de empleado (``EMP-0004``), fechas o montos con PII. Se enmascara del
dato más largo al más corto (``email``, ``curp``, ``rfc``, ``clabe``, ``card``,
``phone``) para que un RFC dentro de una CURP o una CLABE de 18 dígitos no se
cuenten dos veces.
"""

import re
from dataclasses import dataclass
from typing import Callable, Iterable

EMAIL = "email"
PHONE = "phone"
CURP = "curp"
RFC = "rfc"
CARD = "card"
CLABE = "clabe"

# Orden fijo en el que se informan los tipos.
TYPE_ORDER = (EMAIL, PHONE, CURP, RFC, CARD, CLABE)

PLACEHOLDERS = {
    EMAIL: "[EMAIL]",
    PHONE: "[PHONE]",
    CURP: "[CURP]",
    RFC: "[RFC]",
    CARD: "[CARD]",
    CLABE: "[CLABE]",
}

# Sin cuantificadores anidados ambiguos: el tiempo crece de forma lineal.
_PATTERNS = {
    EMAIL: re.compile(r"(?<![\w.%+-])[\w.%+-]+@[\w-]+(?:\.[\w-]+)+"),
    CURP: re.compile(
        r"(?<!\w)[A-Z]{4}\d{6}[HMX][A-Z]{5}[A-Z0-9]\d(?!\w)", re.IGNORECASE
    ),
    RFC: re.compile(r"(?<!\w)[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}(?!\w)", re.IGNORECASE),
    CLABE: re.compile(r"(?<![\w-])\d{18}(?![\w-])"),
    CARD: re.compile(r"(?<![\w-])\d(?:[ -]?\d){12,18}(?![\w-])"),
    PHONE: re.compile(
        r"(?<![\w+-])(?:\+?52[ -]?)?"
        r"(?:\d{3}[ -]?\d{3}|\d{2}[ -]?\d{4})[ -]?\d{4}(?![\w-])"
    ),
}

# Del más largo al más corto: así un dato no se cuenta con dos tipos.
_MASK_ORDER = (EMAIL, CURP, RFC, CLABE, CARD, PHONE)

_DIGITS = re.compile(r"\D")


@dataclass(frozen=True)
class MaskResult:
    """Texto con la PII enmascarada y los tipos que se encontraron.

    :param text: Texto con cada dato reemplazado por ``[EMAIL]``, ``[PHONE]``...
    :type text: str
    :param types: Tipos encontrados, sin repetir, en el orden de ``TYPE_ORDER``
    :type types: tuple[str, ...]
    """

    text: str
    types: tuple[str, ...]


def luhn_ok(digits: str) -> bool:
    """Indica si una cadena de dígitos pasa el algoritmo de Luhn.

    :param digits: Solo dígitos, sin espacios ni guiones
    :type digits: str
    :return: ``True`` si la suma de control es válida
    :rtype: bool
    """
    if not digits or not digits.isdigit():
        return False
    total = 0
    for position, char in enumerate(reversed(digits)):
        value = int(char)
        if position % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def _replacer(kind: str, found: set[str]) -> Callable[[re.Match[str]], str]:
    """Crea la función de reemplazo de un tipo que anota si hubo coincidencia.

    Para ``card`` solo cuenta el número si pasa el algoritmo de Luhn; si no,
    deja el texto como estaba.

    :param kind: Tipo de dato del patrón
    :type kind: str
    :param found: Conjunto donde se anotan los tipos encontrados
    :type found: set[str]
    :return: Función para ``re.sub``
    :rtype: Callable[[re.Match[str]], str]
    """

    def replace(match: re.Match[str]) -> str:
        """Devuelve el marcador del tipo, o el texto original si no aplica."""
        if kind == CARD and not luhn_ok(_DIGITS.sub("", match.group(0))):
            return match.group(0)
        found.add(kind)
        return PLACEHOLDERS[kind]

    return replace


def _ordered(found: Iterable[str]) -> tuple[str, ...]:
    """Ordena los tipos según ``TYPE_ORDER`` y quita repetidos.

    :param found: Tipos encontrados
    :type found: Iterable[str]
    :return: Tipos únicos en orden fijo
    :rtype: tuple[str, ...]
    """
    present = set(found)
    return tuple(kind for kind in TYPE_ORDER if kind in present)


def mask(text: str) -> MaskResult:
    """Reemplaza cada dato de PII por su marcador.

    :param text: Texto a revisar
    :type text: str
    :return: Texto enmascarado y tipos encontrados (nunca los valores)
    :rtype: MaskResult
    """
    found: set[str] = set()
    masked = text
    for kind in _MASK_ORDER:
        masked = _PATTERNS[kind].sub(_replacer(kind, found), masked)
    return MaskResult(text=masked, types=_ordered(found))


def detect(text: str) -> tuple[str, ...]:
    """Devuelve los tipos de PII presentes en un texto.

    :param text: Texto a revisar
    :type text: str
    :return: Tipos únicos en el orden ``email, phone, curp, rfc, card, clabe``
    :rtype: tuple[str, ...]
    """
    return mask(text).types


def detect_all(texts: Iterable[str]) -> tuple[str, ...]:
    """Une los tipos de PII de varios textos.

    :param texts: Textos a revisar (pregunta e historial, por ejemplo)
    :type texts: Iterable[str]
    :return: Tipos únicos en orden fijo
    :rtype: tuple[str, ...]
    """
    found: list[str] = []
    for text in texts:
        found.extend(detect(text))
    return _ordered(found)
