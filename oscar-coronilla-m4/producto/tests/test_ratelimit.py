"""Pruebas de ``app.ratelimit``: ventana deslizante de 60 s por cliente.

Contrato: ``RateLimiter(limit, clock).check(client)`` devuelve una decisión con
``allowed`` y ``retry_after`` (segundos enteros, 1 o más, cuando se niega).
"""

from app.ratelimit import RateLimiter


def test_retry_after_is_rounded_up_and_never_zero(fake_clock):
    limiter = RateLimiter(1, fake_clock)
    assert limiter.check("web").allowed

    fake_clock.advance(59.5)
    decision = limiter.check("web")

    assert decision.allowed is False
    assert decision.retry_after == 1
    assert isinstance(decision.retry_after, int)
