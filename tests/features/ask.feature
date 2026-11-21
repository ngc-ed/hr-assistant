Feature: Ask the HR assistant about employees
  As a member of the HR staff
  I want to ask questions about employees
  So that I get answers from the employee directory

  Background:
    Given the HR assistant runs with the fake model

  Scenario: Asking for an existing employee names that employee
    When I ask "¿Quién es EMP-0004?"
    Then the response status is 200
    And the answer mentions "Jorge Díaz"
    And the tools used are "get_employee"
    And the number of steps is 2

  Scenario: Asking for an unknown employee says it does not exist
    When I ask "¿Quién es EMP-0000?"
    Then the response status is 200
    And the answer mentions "No existe un empleado con id EMP-0000"

  Scenario: Asking for a department lists its people
    When I ask "¿Quiénes trabajan en Finanzas?"
    Then the response status is 200
    And the answer mentions "Sofía Gómez"
    And the tools used are "search_by_department"

  Scenario: A question without an id or department gets the no-data answer
    When I ask "Hola, ¿cómo estás?"
    Then the response status is 200
    And the answer is "No encontré datos para responder. Solo atiendo preguntas de Recursos Humanos. Pregunta por un id de empleado como EMP-0001 o por un departamento."
    And the number of steps is 1

  Scenario: A blank question is rejected
    When I ask "   "
    Then the response status is 422

  Scenario: A question longer than the limit is rejected
    When I ask a question of 2001 characters
    Then the response status is 422

  Scenario: The history comes from the client and is not stored
    Given the model is observed by a spy
    When I ask "¿Quién es EMP-0004?" with the history "Hola"
    And I ask "¿Quién es EMP-0001?"
    Then the model never saw "Hola" in the second request

  Scenario: The step cap stops the loop with the exact message
    Given the agent is limited to 1 step
    When I ask "¿Quién es EMP-00045?"
    Then the response status is 200
    And the answer is "No pude completar la respuesta. Intenta con una pregunta más concreta."
    And the number of steps is 1
