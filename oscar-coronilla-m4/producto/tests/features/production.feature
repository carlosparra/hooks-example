Feature: Only clients with a key can use the assistant, and nobody can abuse it
  As the owner of the assistant published on the internet
  I want every client to use its own key, a limit of requests and safe settings
  So that strangers cannot use it, nobody can exhaust it and secrets never leak

  Scenario Outline: A request without a valid key is rejected
    Given the assistant is running with a captured log
    When I call <method> "<path>" with <credential>
    Then the response status is 401
    And the detail is "invalid or missing API key"
    And the log does not contain the key that was sent

    Examples:
      | method | path     | credential  |
      | POST   | /ask     | no key      |
      | GET    | /metrics | a wrong key |

  Scenario: A client with a valid key is answered and named in the log
    Given the assistant is running with a captured log
    When I ask "¿Quién es EMP-0004?" with the valid key
    Then the response status is 200
    And the "request", "agent_run" and "audit" events name the client "tests"
    And the log does not contain the key that was sent

  Scenario: The page, the health check and the docs need no key
    Given the assistant is running with a captured log
    When I open "/", "/health" and "/docs" without a key
    Then every response status is 200
    And the home page has the API key field

  Scenario: A client that asks too often is told when to retry
    Given the assistant is running with a limit of 2 requests per minute
    When the client "tests" asks 2 questions
    And 20 seconds pass
    And the client "tests" asks 1 question
    Then the response status is 429
    And the detail is "rate limit exceeded"
    And the response asks to retry after 40 seconds

  Scenario: The limit frees up once the minute has passed
    Given the assistant is running with a limit of 2 requests per minute
    When the client "tests" asks 2 questions
    And 61 seconds pass
    And the client "tests" asks 1 question
    Then the response status is 200

  Scenario: A client at its limit does not block another client
    Given the assistant is running with a limit of 2 requests per minute
    When the client "tests" asks 3 questions
    And the client "other" asks 1 question
    Then the response status is 200

  Scenario Outline: Production refuses to start with an unsafe configuration
    Given a safe production configuration
    When the configuration <change>
    Then the assistant refuses to start

    Examples:
      | change                                |
      | uses the fake model                   |
      | has no API keys                       |
      | has a key of 15 characters            |
      | sends traces without hiding the texts |

  Scenario: Production starts with a safe configuration
    Given a safe production configuration
    Then the assistant starts and answers the health check
