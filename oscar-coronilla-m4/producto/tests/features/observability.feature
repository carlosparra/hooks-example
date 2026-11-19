Feature: Every request can be traced and measured
  As a support engineer
  I want each request to have an id, a JSON log and process metrics
  So that I can answer with data what happened with request X

  Scenario: A response without a client id gets a generated UUID
    Given the assistant is running with a captured log
    When I check the health
    Then the response request id is a UUID

  Scenario: The client request id is returned in the header and the body
    Given the assistant is running with a captured log
    When I send "¿Quién es EMP-0004?" with the request id "demo-123"
    Then the response request id is "demo-123"
    And the body request id is "demo-123"

  Scenario: An invalid client request id is replaced by a UUID
    Given the assistant is running with a captured log
    When I check the health with the request id "id with spaces"
    Then the response request id is a UUID

  Scenario: A question leaves one event of each kind without personal text
    Given the assistant is running with a captured log
    When I send "¿Quién es EMP-0004?" with the request id "trace-42"
    Then the log has 1 "request" event
    And the log has 1 "agent_run" event
    And the log has 1 "audit" event
    And the audit event names the tool "get_employee"
    And every event has the service "hr-assistant" and the request id "trace-42"
    And the log does not contain the question or the answer

  Scenario: A failing model returns an internal error with its request id
    Given the assistant is running with a broken model
    When I send "¿Quién es EMP-0004?" with the request id "fail-1"
    Then the response status is 500
    And the body is the internal error with the request id "fail-1"
    And the log has 1 "error" event
    And the error event has the type "RuntimeError"
    And the log does not contain the error message

  Scenario: The metrics report requests, tokens and the SLO
    Given the assistant is running with a captured log
    When I send "¿Quién es EMP-0004?" with the request id "metrics-1"
    And I read the metrics
    Then the metrics count at least 1 request
    And the metrics report input tokens
    And the SLO result is a boolean
