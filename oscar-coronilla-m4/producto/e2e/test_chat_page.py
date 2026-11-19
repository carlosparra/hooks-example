"""Pruebas de punta a punta de la página del HR Assistant con el modelo simulado.

La verificación arranca el producto, pasa la URL base con ``--base-url`` y pone la
clave del cliente en la variable ``E2E_API_KEY``. La clave nunca se escribe aquí.
"""

import os
import re

from playwright.sync_api import Page, expect

UUID_PATTERN = (
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)
REQUEST_ID_PATTERN = re.compile(rf"request_id:\s*{UUID_PATTERN}", re.IGNORECASE)
SPANISH_ERROR_PATTERN = re.compile(r"pregunta", re.IGNORECASE)
INVALID_KEY_MESSAGE = "Clave inválida"
SENSITIVE_DATA_MESSAGE = (
    "Tu pregunta contiene datos sensibles; elimínalos y vuelve a intentar"
)
# Correo de ejemplo (dominio reservado): no es un dato real de nadie.
QUESTION_WITH_EMAIL = "¿Quién es EMP-0001? Mi correo es persona@example.com"


def valid_api_key() -> str:
    """Devuelve la clave válida que pone la verificación.

    :return: Clave del cliente leída de ``E2E_API_KEY``
    :rtype: str
    """
    return os.environ["E2E_API_KEY"]


def enter_api_key(page: Page, api_key: str) -> None:
    """Escribe la clave en su campo de la página.

    :param page: Página de Playwright
    :type page: Page
    :param api_key: Clave que se escribe en el campo
    :type api_key: str
    """
    page.get_by_test_id("api-key").fill(api_key)


def ask(page: Page, question: str) -> None:
    """Escribe una pregunta en el campo y la envía.

    :param page: Página de Playwright
    :type page: Page
    :param question: Texto de la pregunta
    :type question: str
    """
    page.get_by_test_id("question").fill(question)
    page.get_by_test_id("send").click()


def open_page_with_valid_key(page: Page) -> None:
    """Abre la página y escribe la clave válida.

    :param page: Página de Playwright
    :type page: Page
    """
    page.goto("/")
    enter_api_key(page, valid_api_key())


def test_asking_a_question_shows_the_answer_and_its_request_id(page: Page) -> None:
    """Una pregunta enviada muestra la respuesta y su request_id."""
    open_page_with_valid_key(page)
    ask(page, "¿Quién es EMP-0001?")
    conversation = page.get_by_test_id("answer")
    expect(conversation).to_contain_text("Ana López")
    expect(conversation).to_contain_text(REQUEST_ID_PATTERN)


def test_an_empty_question_shows_an_error_message_in_spanish(page: Page) -> None:
    """Una pregunta vacía muestra un mensaje de error en español."""
    open_page_with_valid_key(page)
    ask(page, "   ")
    conversation = page.get_by_test_id("answer")
    expect(conversation).not_to_be_empty()
    expect(conversation).to_contain_text(SPANISH_ERROR_PATTERN)


def test_a_second_question_keeps_the_previous_conversation_on_screen(
    page: Page,
) -> None:
    """La segunda pregunta no borra la conversación anterior."""
    open_page_with_valid_key(page)
    conversation = page.get_by_test_id("answer")
    ask(page, "¿Quién es EMP-0001?")
    expect(conversation).to_contain_text("Ana López")
    ask(page, "¿Quién es EMP-0002?")
    expect(conversation).to_contain_text("Luis Pérez")
    expect(conversation).to_contain_text("EMP-0001")
    expect(conversation).to_contain_text("Ana López")


def test_a_wrong_api_key_shows_an_invalid_key_message(page: Page) -> None:
    """Una clave equivocada muestra «Clave inválida»."""
    page.goto("/")
    # Se deriva de la válida para que sea distinta sin escribir ninguna clave aquí.
    enter_api_key(page, valid_api_key() + "-wrong")
    ask(page, "¿Quién es EMP-0001?")
    conversation = page.get_by_test_id("answer")
    expect(conversation).to_contain_text(INVALID_KEY_MESSAGE)
    expect(conversation).not_to_contain_text("Ana López")


def test_a_question_with_an_email_shows_the_sensitive_data_message_without_an_answer(
    page: Page,
) -> None:
    """Una pregunta con un correo muestra el aviso de datos sensibles.

    Además, no aparece ninguna respuesta del modelo.
    """
    open_page_with_valid_key(page)
    ask(page, QUESTION_WITH_EMAIL)
    conversation = page.get_by_test_id("answer")
    expect(conversation).to_contain_text(SENSITIVE_DATA_MESSAGE)
    # Sin el bloqueo, el modelo simulado respondería con el nombre de EMP-0001.
    expect(conversation).not_to_contain_text("Ana López")
