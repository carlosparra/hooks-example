Feature: HR Assistant answers questions about employees
  As a member of the HR staff
  I want to ask questions about employees from a web page
  So that I get answers from the employee directory

  Scenario: Asking for an existing employee names the employee
    Given the assistant is running
    When I ask "¿Quién es EMP-0004?"
    Then the request succeeds
    And the answer contains "Jorge Díaz"
    And the tools used are "get_employee"
    And the agent took 2 steps

  Scenario: Asking for an unknown employee says it does not exist
    Given the assistant is running
    When I ask "¿Quién es EMP-9999?"
    Then the request succeeds
    And the answer contains "no existe"
    And the tools used are "get_employee"

  Scenario: Asking for a department lists its people
    Given the assistant is running
    When I ask "¿Quiénes trabajan en Finanzas?"
    Then the request succeeds
    And the answer contains "Sofía Gómez"
    And the tools used are "search_by_department"

  Scenario: A question without employee or department gets the help answer
    Given the assistant is running
    When I ask "Hola, ¿cómo estás?"
    Then the request succeeds
    And the answer is "Pregúntame por un empleado (EMP-0001) o un departamento."
    And no tools were used

  Scenario: The step cap stops the loop with the exact message
    Given the assistant is running with at most 1 step
    When I ask "¿Quién es EMP-0004?"
    Then the request succeeds
    And the answer is "No pude completar la respuesta. Intenta con una pregunta más concreta."
    And the agent took 1 steps

  Scenario Outline: Invalid questions are rejected
    Given the assistant is running
    When I send a <kind> question
    Then the request is rejected as invalid

    Examples:
      | kind     |
      | empty    |
      | blank    |
      | too long |

  Scenario: The history comes from the client and is not stored
    Given the assistant is running with a recording model
    When I send the history "Hola" and ask "¿Quién es EMP-0004?"
    And I ask "¿Quién es EMP-0004?"
    Then the first model call received the history and the question
    And the second model call received only the question

  Scenario: The health check reports the process
    Given the assistant is running
    When I check the health
    Then the health status is "ok" with the process id

  Scenario: The home page has the question form
    Given the assistant is running
    When I open the home page
    Then the page has the elements "question", "send" and "answer"
