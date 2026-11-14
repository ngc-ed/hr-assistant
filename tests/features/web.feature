Feature: Web page and health check
  As a member of the HR staff
  I want a web page and a health endpoint
  So that I can use the assistant and operators can check it is alive

  Scenario: The health endpoint reports ok with the process id
    Given the HR assistant is running
    When I open "/health"
    Then the status is "ok"
    And the response includes the process id

  Scenario: The home page has the question form
    Given the HR assistant is running
    When I open "/"
    Then the page contains the test id "question"
    And the page contains the test id "send"
    And the page contains the test id "answer"
