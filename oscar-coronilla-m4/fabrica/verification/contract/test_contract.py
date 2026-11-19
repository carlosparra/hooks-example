"""Contrato de la sesión 1: lo que el producto debe hacer, visto desde afuera."""


def ask(api, question, **extra):
    return api.post("/ask", json={"question": question, **extra})


def test_health_answers_ok(api):
    response = api.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_home_page_has_the_question_form(api):
    page = api.get("/").text
    for test_id in ("question", "send", "answer"):
        assert f'data-testid="{test_id}"' in page


def test_asking_for_an_employee_uses_get_employee(api):
    body = ask(api, "¿Quién es EMP-0004?").json()
    assert "Jorge Díaz" in body["answer"]
    assert body["tools_used"] == ["get_employee"]
    assert body["steps"] == 2


def test_asking_for_a_department_lists_its_people(api):
    body = ask(api, "¿Quiénes trabajan en Finanzas?").json()
    assert "Sofía Gómez" in body["answer"]
    assert body["tools_used"] == ["search_by_department"]


def test_unknown_employee_still_gets_an_answer(api):
    assert ask(api, "¿Quién es EMP-9999?").status_code == 200


def test_empty_question_is_rejected(api):
    assert ask(api, "").status_code == 422


def test_too_long_question_is_rejected(api):
    assert ask(api, "a" * 2001).status_code == 422


def test_history_comes_from_the_client(api):
    history = [{"role": "user", "content": "Hola"}]
    assert ask(api, "¿Quién es EMP-0004?", history=history).status_code == 200


def test_the_step_cap_stops_the_loop(api_one_step):
    body = ask(api_one_step, "¿Quién es EMP-0004?").json()
    assert body["steps"] == 1
    assert "No pude completar" in body["answer"]
