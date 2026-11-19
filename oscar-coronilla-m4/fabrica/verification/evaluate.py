"""Compara costo y calidad: línea base contra la configuración con palancas.

Corre ``verification/eval_set.json`` contra el producto dos veces, con el modelo
simulado. Cada pregunta lleva un historial de relleno, como una conversación
larga. Pasa solo si la calidad no baja y el costo sí baja.
"""

import json
import sys
from pathlib import Path

from verification.server import running_product

EVAL_SET = Path(__file__).resolve().parent / "eval_set.json"
BASELINE = {"ROUTING": "false", "HISTORY_WINDOW": "1000"}
HISTORY = [
    {"role": role, "content": text}
    for _ in range(5)
    for role, text in (
        ("user", "Hola, necesito datos de un empleado del directorio de RH."),
        ("assistant", "Claro, dime el número de empleado o el departamento."),
    )
]


def is_correct(answer: str, case: dict) -> bool:
    """Indica si la respuesta cumple lo que pide el caso de evaluación."""
    if "must_include" in case:
        return all(text in answer for text in case["must_include"])
    return any(text.lower() in answer.lower() for text in case["any_of"])


def measure(client, cases: list[dict]) -> dict:
    """Pregunta cada caso y suma calidad y costo.

    :return: ``quality`` (fracción correcta), ``cost_usd`` e ``input_tokens``
    :rtype: dict
    """
    correct, cost, tokens = 0, 0.0, 0
    for case in cases:
        body = client.post(
            "/ask", json={"question": case["question"], "history": HISTORY}
        ).json()
        correct += is_correct(body["answer"], case)
        cost += body["cost_usd"]
        tokens += body["input_tokens"]
    return {"quality": correct / len(cases), "cost_usd": cost, "input_tokens": tokens}


def verdict(baseline: dict, levers: dict) -> bool:
    """La regla de la sesión: misma calidad o mejor, y menos costo."""
    return levers["quality"] >= baseline["quality"] and (
        levers["cost_usd"] < baseline["cost_usd"]
    )


def main() -> int:
    """Mide las dos configuraciones, imprime la tabla y decide."""
    cases = json.loads(EVAL_SET.read_text(encoding="utf-8"))
    with running_product(8767, **BASELINE) as client:
        baseline = measure(client, cases)
    with running_product(8768) as client:
        levers = measure(client, cases)
    for name, result in (("baseline", baseline), ("levers", levers)):
        print(
            f"{name:9} quality={result['quality']:.0%} "
            f"cost_usd={result['cost_usd']:.6f} input_tokens={result['input_tokens']}"
        )
    passed = verdict(baseline, levers)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
