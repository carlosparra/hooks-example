Feature: Every answer is cheaper without getting worse
  As the owner of the assistant budget
  I want each question to use the cheapest model that can answer it and report its cost
  So that I can lower the bill and prove that quality did not drop

  Scenario: A simple question goes to the small model and has a cost
    Given the assistant is running with the simulated models
    When I ask "¿Quién es EMP-0004?"
    Then the response status is 200
    And the answer used the small model
    And the route is "short_question"
    And the cost is greater than zero

  Scenario: A question that asks to compare goes to the large model
    Given the assistant is running with the simulated models
    When I ask "Compara a los empleados del departamento de Finanzas"
    Then the answer used the large model
    And the route is "keyword"

  Scenario: A long question goes to the large model
    Given the assistant is running with the simulated models
    When I ask a question of 81 characters about "EMP-0004"
    Then the answer used the large model
    And the route is "long_question"

  Scenario: With routing turned off every question goes to the large model
    Given the assistant is running with routing turned off
    When I ask "¿Quién es EMP-0004?"
    Then the answer used the large model
    And the route is "routing_off"

  Scenario: Only the last messages of the history reach the model
    Given the assistant is running with a recording model and a history window of 6
    When I ask "¿Quién es EMP-0004?" after 10 history messages
    Then the model received 7 messages
    And the last message the model received is "¿Quién es EMP-0004?"

  Scenario: A failing gateway returns model unavailable with the request id
    Given the assistant is running with a gateway that fails
    When I ask "¿Quién es EMP-0004?" with the request id "gw-down-1"
    Then the response status is 502
    And the body is model unavailable with the request id "gw-down-1"
    And the log has 1 "error" event
    And the log does not contain the gateway token

  Scenario: Answers served from the gateway cache cost nothing
    Given the assistant is running with a gateway that answers from its cache
    When I ask "Hola"
    Then the response status is 200
    And every call was cached
    And the cost is zero

  Scenario: The metrics add up the cost of every answer
    Given the assistant is running with the simulated models
    When I ask "¿Quién es EMP-0004?"
    And I ask "Compara a los empleados del departamento de Finanzas"
    And I read the metrics
    Then the metrics cost is the sum of both answers
