Feature: Personal data never reaches the model nor leaves in an answer
  As the owner of the HR assistant
  I want questions with personal data blocked and answers with personal data masked
  So that sensitive data is never sent to the model, shown or written to the log

  Scenario Outline: A question with personal data is rejected without calling the model
    Given the assistant is running with a recording model
    When I ask "<question>"
    Then the response status is 422
    And the detail is "sensitive data detected: <types>"
    And the response has a request id
    And the response does not contain "<value>"
    And the model was not called

    Examples:
      | question                                                     | value                 | types       |
      | ¿Quién tiene el correo ana.lopez@empresa.com?                | ana.lopez@empresa.com | email       |
      | Llama al +52 442-123-4567 y dime quién es                    | 442-123-4567          | phone       |
      | Mi CURP es LOPA900101MDFPRN09 y mi CLABE 002010077777777774  | LOPA900101MDFPRN09    | curp, clabe |

  Scenario: Personal data in an old history message is rejected even outside the window
    Given the assistant is running with a recording model and a history window of 2
    When I ask "¿Quién es EMP-0004?" after 4 history messages, the first with "ana.lopez@empresa.com"
    Then the response status is 422
    And the detail is "sensitive data detected: email"
    And the model was not called

  Scenario: An employee number is not personal data
    Given the assistant is running with the simulated models
    When I ask "¿Quién es EMP-0004?"
    Then the response status is 200
    And the answer contains "Jorge Díaz"
    And the masked types are ""

  Scenario: Personal data in the model answer is masked and audited
    Given the assistant is running with a model that answers "Escribe a jorge.diaz@empresa.com o llama al 442 123 4567."
    When I ask "¿Cómo contacto a Jorge?"
    Then the response status is 200
    And the answer contains "[EMAIL]"
    And the answer contains "[PHONE]"
    And the masked types are "email, phone"
    And the response does not contain "jorge.diaz@empresa.com"
    And the log has a "pii_detected" event from the "output" with types "email, phone"
    And the log does not contain "jorge.diaz@empresa.com"
    And the metrics show 0 blocked and 1 masked answers

  Scenario: An empty model answer becomes the step limit message
    Given the assistant is running with a model that answers with an empty text
    When I ask "¿Quién es EMP-0004?"
    Then the response status is 200
    And the answer is the step limit message

  Scenario: A blocked question is audited and counted without its value
    Given the assistant is running with a recording model
    When I ask "Mi correo es prueba@empresa.com"
    Then the response status is 422
    And the log has a "pii_detected" event from the "input" with types "email"
    And the log does not contain "prueba@empresa.com"
    And the metrics show 1 blocked and 0 masked answers

  Scenario: With detection turned off in development a question with an email is answered
    Given the assistant is running with a recording model and PII detection turned off
    When I ask "Mi correo es prueba@empresa.com"
    Then the response status is 200
    And the model was called

  Scenario: Production refuses to start without PII detection
    Given a safe production configuration
    When PII detection is turned off
    Then the assistant refuses to start
