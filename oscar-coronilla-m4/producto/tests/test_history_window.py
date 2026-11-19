"""Pruebas de la ventana de historial que ``POST /ask`` manda al modelo."""

SMALL_MODEL = "@cf/meta/llama-3.1-8b-instruct-fast"
LARGE_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"


def test_window_of_zero_sends_only_the_question(
    make_cost_app, make_cost_settings, scripted_model
):
    # Cuidado: ``history[-0:]`` devolveria todo el historial.
    recorder = scripted_model(['{"answer": "Listo"}'])
    observed = make_cost_app(
        settings=make_cost_settings(history_window=0),
        models={SMALL_MODEL: recorder, LARGE_MODEL: recorder},
    )
    history = [{"role": "user", "content": "antes"}] * 4

    response = observed.client.post(
        "/ask", json={"question": "Hola", "history": history}
    )

    assert response.status_code == 200
    assert recorder.calls[0] == [{"role": "user", "content": "Hola"}]
