Feature: Production security and compliance
  As an API provider
  I want to protect the API with authentication and rate limiting
  So that each client is identified and protected against abuse

  Background:
    Given the HR assistant runs with the fake model
    And API keys are configured for two clients

  Scenario: Valid API key allows access
    When I ask "¿Quién es EMP-0004?" with a valid API key
    Then the response status is 200
    And the answer mentions "Jorge Díaz"

  Scenario: Invalid API key is rejected
    When I send a request to "/ask" with an invalid API key
    Then the response status is 401
    And the response detail is "invalid or missing API key"

  Scenario: Missing API key header is rejected
    When I send a request to "/ask" without the API key header
    Then the response status is 401
    And the response detail is "invalid or missing API key"

  Scenario: Public endpoints do not require API key
    When I send a GET request to "/" without the API key header
    Then the response status is 200

  Scenario: Health check endpoint does not require API key
    When I send a GET request to "/health" without the API key header
    Then the response status is 200

  Scenario: Metrics endpoint requires API key
    When I send a GET request to "/metrics" without the API key header
    Then the response status is 401
    And the response detail is "invalid or missing API key"

  Scenario: Metrics endpoint with valid key returns data
    When I send a GET request to "/metrics" with a valid API key
    Then the response status is 200

  Scenario: Rate limit is enforced per client per minute
    Given the rate limit is set to 3 requests per minute
    When I send 4 requests to "/ask" with a valid API key within 60 seconds
    Then the first 3 requests succeed
    And the 4th request returns 429
    And the response detail is "rate limit exceeded"

  Scenario: Rate limit includes Retry-After header
    Given the rate limit is set to 2 requests per minute
    When I send 3 requests to "/ask" with a valid API key within 60 seconds
    Then the 3rd request returns 429
    And the "Retry-After" header is set to a positive integer

  Scenario: Rate limit allows requests again after the window passes
    Given the rate limit is set to 2 requests per minute
    When I send 2 requests to "/ask" with a valid API key within 60 seconds
    And I send 1 more request to "/ask" with the same key
    And the clock advances 61 seconds
    And I send 1 more request to "/ask" with the same key
    Then the request number 3 returns 429
    And the request number 4 returns 200

  Scenario: One client reaching its limit does not block another client
    Given the rate limit is set to 1 requests per minute
    When I send a request to "/ask" with a valid API key for client "alice"
    And I send a request to "/ask" with a valid API key for client "alice"
    And I send a request to "/ask" with a valid API key for client "bob"
    Then the request number 1 returns 200
    And the request number 2 returns 429
    And the request number 3 returns 200

  Scenario: The client name is written to the agent_run and audit log events
    When I send a request to "/ask" with a valid API key for client "alice"
    Then the response status is 200
    And the "agent_run" log event has the client "alice"
    And the "audit" log event has the client "alice"
    And the log does not contain the API key

  Scenario: Empty API keys string prevents startup in production
    When I try to start the app with ENVIRONMENT set to production
    And API_KEYS is empty
    Then the app fails to start
    And the error message does not expose the empty value

  Scenario: Short API key prevents startup in production
    When I try to start the app with ENVIRONMENT set to production
    And API_KEYS contains a key shorter than 16 characters
    Then the app fails to start
    And the error message does not expose the actual key

  Scenario: Fake model provider prevents startup in production
    When I try to start the app with ENVIRONMENT set to production
    And MODEL_PROVIDER is set to fake
    Then the app fails to start

  Scenario: Tracing without HIDE_INPUTS prevents startup in production
    When I try to start the app with ENVIRONMENT set to production
    And tracing is enabled
    And HIDE_INPUTS is set to false
    Then the app fails to start

  Scenario: Tracing without HIDE_OUTPUTS prevents startup in production
    When I try to start the app with ENVIRONMENT set to production
    And tracing is enabled
    And HIDE_OUTPUTS is set to false
    Then the app fails to start

  Scenario: Valid production configuration allows startup
    When I try to start the app with ENVIRONMENT set to production
    And API_KEYS contains valid 16-character keys
    And MODEL_PROVIDER is not fake
    And HIDE_INPUTS is true
    And HIDE_OUTPUTS is true
    Then the app starts successfully

  Scenario: API keys are never exposed in error messages
    When I send a request to "/ask" with an invalid API key
    Then the response status is 401
    And the response detail is "invalid or missing API key"
