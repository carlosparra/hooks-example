"""Pruebas de la regla de costo y calidad, sin correr el producto."""

from verification import evaluate


class FakeClient:
    """Cliente que responde siempre lo mismo, para medir sin servidor."""

    def __init__(self, answer, cost):
        self.answer, self.cost = answer, cost

    def post(self, _path, json):
        assert json["history"]
        return self

    def json(self):
        return {"answer": self.answer, "cost_usd": self.cost, "input_tokens": 10}


def test_must_include_needs_every_text():
    case = {"must_include": ["Ana", "Jorge"]}
    assert evaluate.is_correct("Ana y Jorge", case)
    assert not evaluate.is_correct("Ana", case)


def test_any_of_needs_one_text_ignoring_case():
    assert evaluate.is_correct("Ya NO EXISTE", {"any_of": ["no existe"]})


def test_measure_adds_quality_cost_and_tokens():
    cases = [{"question": "q", "must_include": ["Ana"]}] * 2
    assert evaluate.measure(FakeClient("Ana", 0.5), cases) == {
        "quality": 1.0, "cost_usd": 1.0, "input_tokens": 20,
    }


def test_levers_must_be_cheaper_without_losing_quality():
    baseline = {"quality": 0.9, "cost_usd": 1.0}
    assert evaluate.verdict(baseline, {"quality": 0.9, "cost_usd": 0.4})
    assert not evaluate.verdict(baseline, {"quality": 0.8, "cost_usd": 0.1})
    assert not evaluate.verdict(baseline, {"quality": 1.0, "cost_usd": 1.0})
