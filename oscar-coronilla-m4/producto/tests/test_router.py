"""Pruebas de ``app.router``: la regla que elige el modelo de cada pregunta."""

from app.config import Settings
from app.router import route

SMALL_MODEL = "@cf/meta/llama-3.1-8b-instruct-fast"
LARGE_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"


def test_keywords_are_found_without_accents_or_capitals():
    settings = Settings()

    without_accent = route("¿POR QUE se fue EMP-0003?", settings)
    summary = route("Resume el área de Ventas", settings)

    assert (without_accent.model, without_accent.reason) == (LARGE_MODEL, "keyword")
    assert (summary.model, summary.reason) == (LARGE_MODEL, "keyword")


def test_questions_up_to_the_character_limit_go_to_the_small_model():
    settings = Settings(router_max_chars=80)

    at_limit = route("a" * 80, settings)
    over_limit = route("a" * 81, settings)

    assert (at_limit.model, at_limit.reason) == (SMALL_MODEL, "short_question")
    assert (over_limit.model, over_limit.reason) == (LARGE_MODEL, "long_question")


def test_routing_off_sends_even_short_questions_to_the_large_model():
    chosen = route("¿Quién es EMP-0004?", Settings(routing=False))

    assert chosen.model == LARGE_MODEL
    assert chosen.reason == "routing_off"
