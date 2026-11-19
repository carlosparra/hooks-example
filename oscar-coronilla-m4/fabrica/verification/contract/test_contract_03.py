"""Contrato de la sesión 3: cada respuesta dice qué modelo usó y cuánto costó."""


def ask(api, question):
    return api.post("/ask", json={"question": question}).json()


def test_simple_questions_go_to_the_small_model(api):
    body = ask(api, "¿Quién es EMP-0004?")
    assert body["model"] == "@cf/meta/llama-3.1-8b-instruct-fast"
    assert body["cost_usd"] > 0


def test_complex_questions_go_to_the_large_model(api):
    body = ask(api, "Compara a los empleados del departamento de Finanzas")
    assert body["model"] == "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
    assert body["route"]


def test_metrics_add_up_the_cost(api):
    ask(api, "¿Quién es EMP-0004?")
    assert api.get("/metrics").json()["cost_usd"] > 0
