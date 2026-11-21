Feature: Specialists get their data from the code
  When the supervisor decides by rules, the code calls the specialist tool before
  the model, so a small model that only writes text cannot leave the answer without data.

  Background:
    Given an assistant whose model never asks for tools

  Scenario: An employee question is answered with data even if the model never asks for a tool
    When I ask "¿Quién es EMP-0004?"
    Then the response status is 200
    And the tools used include "get_employee"
    And the answer does not mention "get_employee"

  Scenario: A department question is answered with data even if the model never asks for a tool
    When I ask "¿Quién trabaja en Tecnología?"
    Then the response status is 200
    And the tools used include "search_by_department"
    And the answer does not mention "search_by_department"
