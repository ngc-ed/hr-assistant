Feature: Know what happened with any request
  As a support engineer
  I want every request to carry an id, a JSON log and metrics
  So that I can explain with data what happened with request X

  Background:
    Given the HR assistant runs with an observed log

  Scenario: A request without an id gets a generated UUID
    When I open "/health"
    Then the response header X-Request-ID is a valid UUID

  Scenario: A request id sent by the client is returned in header and body
    When I ask "¿Quién es EMP-0004?" with the request id "demo-123"
    Then the response status is 200
    And the response header X-Request-ID is "demo-123"
    And the response body has the request id "demo-123"

  Scenario Outline: An invalid request id is replaced by a UUID
    When I open "/health" with an invalid request id that is <kind>
    Then the response header X-Request-ID is a valid UUID

    Examples:
      | kind      |
      | spaced    |
      | too long  |

  Scenario: A question leaves request and agent_run lines without its text
    When I ask "¿Quién es EMP-0004?"
    Then the log has a "request" line with the response request id
    And the log has an "agent_run" line with the response request id
    And the agent_run line counts the question without its text
    And no log line contains the question or the answer

  Scenario: Every tool call leaves an audit line
    When I ask "¿Quién es EMP-0004?"
    Then the log has an audit line for "get_employee" with employee id "EMP-0004"

  Scenario: A failing model returns a generic 500 with the request id
    Given the model fails with the message "secreto"
    When I ask "¿Quién es EMP-0004?"
    Then the response status is 500
    And the error body says "internal error" with the response request id
    And the log has an error line of type "RuntimeError"
    And no log line contains "secreto"

  Scenario: Metrics report requests, tokens, latency and the SLO
    When I ask "¿Quién es EMP-0004?"
    And I open "/metrics"
    Then the metrics count at least 1 request
    And the metrics report input tokens
    And the metrics report p50 and p95 latency
    And the metrics say whether the SLO is met

  Scenario: The web page shows the request id of each answer
    When I open "/"
    Then the page contains the text "request_id"
    And the page contains the test id "request-id"
