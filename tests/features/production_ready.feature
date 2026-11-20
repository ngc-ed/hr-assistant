Feature: Protect personal data and survive gateway failures
  As the owner of the HR assistant in production
  I want personal data masked, unsafe answers blocked and failures contained
  So that the service can be operated with real people and real traffic

  Background:
    Given the HR assistant runs with an API key and an observed log

  Scenario: Personal data in the question is masked before it reaches the model
    Given a spy model that records the messages it receives
    When I ask "Mi correo es sofia.gomez@example.com y mi RFC es GOMS800101AB1"
    Then the response status is 200
    And the model received "[CORREO]" and "[RFC]" instead of the real values
    And the log has pii_detected lines for "CORREO" and "RFC" on the input
    And the log contains neither "sofia.gomez@example.com" nor "GOMS800101AB1"

  Scenario: Personal data in the answer is masked before it is returned
    Given a model that answers "Escribele a sofia.gomez@example.com"
    When I ask "¿Quién es EMP-0004?"
    Then the response status is 200
    And the answer contains "[CORREO]" and not "sofia.gomez@example.com"
    And the log has pii_detected lines for "CORREO" on the output

  Scenario: An answer that looks like a key is replaced by a safe message
    Given a model that answers "Usa sk-abcdefghijklmnopqrstuvwx para entrar"
    When I ask "¿Quién es EMP-0004?"
    Then the response status is 200
    And the answer is the safe message
    And the log has an output_rejected line with the reason "secret"
    And the log never contains "sk-abcdefghijklmnopqrstuvwx"

  Scenario: A gateway that keeps failing with 503 ends in 502 after the retries
    Given a gateway that fails with 503 on every call and allows 2 retries
    When I ask "¿Quién es EMP-0004?"
    Then the response status is 502
    And the gateway was called 3 times

  Scenario: The dashboard is public but the metrics still need a key
    When I open "/dashboard" without a key
    Then the response status is 200
    And the page is HTML and does not contain the API key
    When I open "/metrics" without a key
    Then the response status is 401
    When I open "/metrics" with the key
    Then the response status is 200
