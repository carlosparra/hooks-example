"""Pruebas de ``app.security``: claves por cliente que nunca se filtran.

Contrato: ``parse_api_keys(raw)`` lee ``cliente:clave,cliente2:clave2`` y lanza
``ValueError`` con el número de la entrada y su largo, nunca su texto.
``ApiKeyAuth(api_keys).identify(header)`` devuelve el nombre del cliente o
``None``.
"""

import pytest

from app.security import ApiKeyAuth, parse_api_keys

WEB_KEY = "web-key-0123456789"
MOBILE_KEY = "mobile-key-0123456789"


def test_keys_with_surrounding_spaces_identify_their_client():
    auth = ApiKeyAuth(parse_api_keys(f" web : {WEB_KEY} , mobile:{MOBILE_KEY} "))

    assert auth.identify(WEB_KEY) == "web"
    assert auth.identify(MOBILE_KEY) == "mobile"


@pytest.mark.parametrize(
    "raw",
    [
        "web:",  # clave vacía
        "web client:abc-0123456789",  # el nombre tiene un espacio
    ],
    ids=["empty key", "client name with forbidden characters"],
)
def test_malformed_api_keys_are_rejected(raw):
    with pytest.raises(ValueError):
        parse_api_keys(raw)


def test_malformed_entry_reports_its_position_and_length_but_never_the_key():
    secret = "secret-value-without-client"

    with pytest.raises(ValueError) as error:
        parse_api_keys(f"web:{WEB_KEY},{secret}")

    message = str(error.value)
    assert "2" in message
    assert str(len(secret)) in message
    assert secret not in message
    assert WEB_KEY not in message


def test_wrong_empty_or_missing_key_identifies_nobody():
    auth = ApiKeyAuth(parse_api_keys(f"web:{WEB_KEY}"))

    assert auth.identify("wrong-key-0123456789") is None
    assert auth.identify("") is None
    assert auth.identify(None) is None
