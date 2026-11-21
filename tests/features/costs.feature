Feature: Make every answer cheaper without making it worse
  As the owner of the HR assistant budget
  I want each answer to say which model it used, why and how much it cost
  So that the cost levers can be measured without lowering quality

  Background:
    Given the HR assistant runs with the simulated models and an observed log

  Scenario: A simple question goes to the small model and has a cost
    When I ask "¿Quién es EMP-0004?"
    Then the response status is 200
    And the answer used the model "@cf/meta/llama-3.1-8b-instruct-fast" with the route "simple"
    And the answer cost is greater than zero

  Scenario: A question with a complex keyword goes to the large model
    When I ask "Compara a los empleados del departamento de Finanzas"
    Then the answer used the model "@cf/meta/llama-3.3-70b-instruct-fp8-fast" with the route "keyword:compara"

  Scenario: A question longer than the router limit goes to the large model
    Given the router limit is 20 characters
    When I ask "¿Quién es EMP-0004 y dónde trabaja?"
    Then the answer used the model "@cf/meta/llama-3.3-70b-instruct-fp8-fast" with the route "long_question"

  Scenario: With routing disabled every question goes to the large model
    Given routing is disabled
    When I ask "¿Quién es EMP-0004?"
    Then the answer used the model "@cf/meta/llama-3.3-70b-instruct-fp8-fast" with the route "routing_disabled"

  Scenario: Only the last messages of the history reach the model
    Given a spy model that counts the messages it receives
    And the history window is 6 messages
    When I ask "¿Quién es EMP-0004?" with a history of 10 messages
    Then the first model call receives 9 messages
    And the agent_run line records 10 history messages and 6 sent

  Scenario: The metrics add up the cost of the answers
    When I ask "¿Quién es EMP-0004?"
    And I open "/metrics"
    Then the metrics report a cost greater than zero

  Scenario: An unavailable model returns 502 with the request id
    Given the model is unavailable
    When I ask "¿Quién es EMP-0004?"
    Then the response status is 502
    And the error body says "model unavailable" with the response request id
    And the log has an error line of type "ModelUnavailableError"

  Scenario: Calls answered from the gateway cache cost nothing
    Given a model whose every call is answered from the cache
    When I ask "¿Quién es EMP-0004?"
    Then the response status is 200
    And the answer has cached calls and costs zero
