"""Pruebas unitarias para compliance checks en configuración de producción."""

import pytest

from app.config import load_settings


class TestProductionComplianceApiKeys:
    """Pruebas de compliance para API_KEYS en producción."""

    def test_production_rejects_empty_api_keys(self):
        """En producción, API_KEYS vacía causa error al arrancar."""
        env = {
            "ENVIRONMENT": "production",
            "API_KEYS": "",
            "MODEL_PROVIDER": "gateway",
            "CF_ACCOUNT_ID": "account-123",
            "CF_GATEWAY_ID": "gateway-123",
            "CF_API_TOKEN": "token-xyz",
        }

        with pytest.raises(ValueError):
            load_settings(env)

    def test_production_rejects_short_api_key(self):
        """En producción, una clave menor de 16 caracteres causa error."""
        env = {
            "ENVIRONMENT": "production",
            "API_KEYS": "client:short",
            "MODEL_PROVIDER": "gateway",
            "CF_ACCOUNT_ID": "account-123",
            "CF_GATEWAY_ID": "gateway-123",
            "CF_API_TOKEN": "token-xyz",
        }

        with pytest.raises(ValueError):
            load_settings(env)

    def test_production_rejects_multiple_keys_one_short(self):
        """En producción, si una clave es corta, falla."""
        env = {
            "ENVIRONMENT": "production",
            "API_KEYS": "client1:validkey1234567,client2:short",
            "MODEL_PROVIDER": "gateway",
            "CF_ACCOUNT_ID": "account-123",
            "CF_GATEWAY_ID": "gateway-123",
            "CF_API_TOKEN": "token-xyz",
        }

        with pytest.raises(ValueError):
            load_settings(env)

    def test_production_accepts_valid_api_keys(self):
        """En producción, claves válidas (>= 16 chars) se aceptan."""
        env = {
            "ENVIRONMENT": "production",
            "API_KEYS": "client1:1234567890123456,client2:abcdefghijklmnop",
            "MODEL_PROVIDER": "gateway",
            "CF_ACCOUNT_ID": "account-123",
            "CF_GATEWAY_ID": "gateway-123",
            "CF_API_TOKEN": "token-xyz",
        }

        settings = load_settings(env)
        assert settings.api_keys is not None

    def test_development_allows_short_api_keys(self):
        """En desarrollo, las claves cortas se permiten."""
        env = {
            "ENVIRONMENT": "development",
            "API_KEYS": "client:short",
            "MODEL_PROVIDER": "fake",
        }

        settings = load_settings(env)
        assert settings.api_keys is not None

    def test_production_error_excludes_key_value(self):
        """El error de compliance nunca expone el valor de la clave."""
        env = {
            "ENVIRONMENT": "production",
            "API_KEYS": "client:mysecretkey123",
            "MODEL_PROVIDER": "gateway",
            "CF_ACCOUNT_ID": "account-123",
            "CF_GATEWAY_ID": "gateway-123",
            "CF_API_TOKEN": "token-xyz",
        }

        with pytest.raises(ValueError) as exc_info:
            load_settings(env)

        error_message = str(exc_info.value)
        assert "mysecretkey123" not in error_message
        assert "secret" not in error_message.lower()


class TestProductionComplianceModelProvider:
    """Pruebas de compliance para MODEL_PROVIDER en producción."""

    def test_production_rejects_fake_model(self):
        """En producción, MODEL_PROVIDER=fake causa error."""
        env = {
            "ENVIRONMENT": "production",
            "API_KEYS": "client:1234567890123456",
            "MODEL_PROVIDER": "fake",
        }

        with pytest.raises(ValueError):
            load_settings(env)

    def test_production_rejects_fake_model_case_insensitive(self):
        """La validación de 'fake' no distingue mayúsculas."""
        env = {
            "ENVIRONMENT": "production",
            "API_KEYS": "client:1234567890123456",
            "MODEL_PROVIDER": "FAKE",
        }

        with pytest.raises(ValueError):
            load_settings(env)

    def test_production_accepts_gateway_model(self):
        """En producción, MODEL_PROVIDER=gateway se acepta."""
        env = {
            "ENVIRONMENT": "production",
            "API_KEYS": "client:1234567890123456",
            "MODEL_PROVIDER": "gateway",
            "CF_ACCOUNT_ID": "account-123",
            "CF_GATEWAY_ID": "gateway-123",
            "CF_API_TOKEN": "token-xyz",
        }

        settings = load_settings(env)
        assert settings.model_provider == "gateway"

    def test_development_allows_fake_model(self):
        """En desarrollo, MODEL_PROVIDER=fake se permite."""
        env = {
            "ENVIRONMENT": "development",
            "MODEL_PROVIDER": "fake",
        }

        settings = load_settings(env)
        assert settings.model_provider == "fake"


class TestProductionComplianceTracing:
    """Pruebas de compliance para trazas en producción."""

    def test_production_rejects_tracing_without_hide_inputs(self):
        """En producción, trazas sin HIDE_INPUTS=true causa error."""
        env = {
            "ENVIRONMENT": "production",
            "API_KEYS": "client:1234567890123456",
            "MODEL_PROVIDER": "gateway",
            "CF_ACCOUNT_ID": "account-123",
            "CF_GATEWAY_ID": "gateway-123",
            "CF_API_TOKEN": "token-xyz",
            "LANGSMITH_API_KEY": "ls-key-123",
            "HIDE_INPUTS": "false",
        }

        with pytest.raises(ValueError):
            load_settings(env)

    def test_production_rejects_tracing_without_hide_outputs(self):
        """En producción, trazas sin HIDE_OUTPUTS=true causa error."""
        env = {
            "ENVIRONMENT": "production",
            "API_KEYS": "client:1234567890123456",
            "MODEL_PROVIDER": "gateway",
            "CF_ACCOUNT_ID": "account-123",
            "CF_GATEWAY_ID": "gateway-123",
            "CF_API_TOKEN": "token-xyz",
            "LANGSMITH_API_KEY": "ls-key-123",
            "HIDE_OUTPUTS": "false",
        }

        with pytest.raises(ValueError):
            load_settings(env)

    def test_production_accepts_tracing_with_both_hidden(self):
        """En producción, trazas con HIDE_INPUTS y HIDE_OUTPUTS=true se aceptan."""
        env = {
            "ENVIRONMENT": "production",
            "API_KEYS": "client:1234567890123456",
            "MODEL_PROVIDER": "gateway",
            "CF_ACCOUNT_ID": "account-123",
            "CF_GATEWAY_ID": "gateway-123",
            "CF_API_TOKEN": "token-xyz",
            "LANGSMITH_API_KEY": "ls-key-123",
            "HIDE_INPUTS": "true",
            "HIDE_OUTPUTS": "true",
        }

        settings = load_settings(env)
        assert settings.langsmith_api_key == "ls-key-123"

    def test_production_allows_tracing_without_langsmith_key(self):
        """En producción, sin LANGSMITH_API_KEY no hay trazas."""
        env = {
            "ENVIRONMENT": "production",
            "API_KEYS": "client:1234567890123456",
            "MODEL_PROVIDER": "gateway",
            "CF_ACCOUNT_ID": "account-123",
            "CF_GATEWAY_ID": "gateway-123",
            "CF_API_TOKEN": "token-xyz",
            "HIDE_INPUTS": "true",
            "HIDE_OUTPUTS": "true",
        }

        settings = load_settings(env)
        assert settings is not None

    def test_development_allows_tracing_without_hide(self):
        """En desarrollo, trazas sin HIDE_INPUTS/HIDE_OUTPUTS se permiten."""
        env = {
            "ENVIRONMENT": "development",
            "MODEL_PROVIDER": "fake",
            "LANGSMITH_API_KEY": "ls-key-123",
            "HIDE_INPUTS": "false",
        }

        settings = load_settings(env)
        assert settings is not None


class TestProductionComplianceIntegration:
    """Pruebas de integración de compliance en producción."""

    def test_full_production_configuration(self):
        """Configuración completa válida en producción."""
        env = {
            "ENVIRONMENT": "production",
            "API_KEYS": "client1:key1234567890123456,client2:key2345678901234567",
            "MODEL_PROVIDER": "gateway",
            "CF_ACCOUNT_ID": "account-123",
            "CF_GATEWAY_ID": "gateway-456",
            "CF_API_TOKEN": "token-xyz",
            "RATE_LIMIT_PER_MINUTE": "30",
            "LANGSMITH_API_KEY": "ls-key-abc",
            "HIDE_INPUTS": "true",
            "HIDE_OUTPUTS": "true",
        }

        settings = load_settings(env)
        assert settings.environment == "production"
        assert settings.api_keys is not None
        assert settings.model_provider == "gateway"

    def test_multiple_compliance_violations_reports_first(self):
        """Si hay múltiples violaciones, reporta la primera."""
        env = {
            "ENVIRONMENT": "production",
            "API_KEYS": "",  # Violación 1
            "MODEL_PROVIDER": "fake",  # Violación 2
        }

        with pytest.raises(ValueError):
            load_settings(env)

    def test_production_error_does_not_expose_sensitive_data(self):
        """Los errores nunca exponen datos sensibles."""
        env = {
            "ENVIRONMENT": "production",
            "API_KEYS": "admin:supersecret123456789",
            "MODEL_PROVIDER": "gateway",
            "CF_ACCOUNT_ID": "account-xyz",
            "CF_GATEWAY_ID": "gateway-abc",
            "CF_API_TOKEN": "token-secret-xyz",
            "LANGSMITH_API_KEY": "ls-key-secret",
            "HIDE_INPUTS": "false",
        }

        with pytest.raises(ValueError) as exc_info:
            load_settings(env)

        error_message = str(exc_info.value)
        assert "supersecret" not in error_message
        assert "token-secret-xyz" not in error_message
        assert "ls-key-secret" not in error_message

    def test_exactly_16_character_key_is_valid(self):
        """Una clave de exactamente 16 caracteres es válida."""
        env = {
            "ENVIRONMENT": "production",
            "API_KEYS": "client:1234567890123456",
            "MODEL_PROVIDER": "gateway",
            "CF_ACCOUNT_ID": "account-123",
            "CF_GATEWAY_ID": "gateway-123",
            "CF_API_TOKEN": "token-xyz",
        }

        settings = load_settings(env)
        assert settings is not None

    def test_15_character_key_is_invalid(self):
        """Una clave de 15 caracteres es inválida."""
        env = {
            "ENVIRONMENT": "production",
            "API_KEYS": "client:123456789012345",
            "MODEL_PROVIDER": "gateway",
            "CF_ACCOUNT_ID": "account-123",
            "CF_GATEWAY_ID": "gateway-123",
            "CF_API_TOKEN": "token-xyz",
        }

        with pytest.raises(ValueError):
            load_settings(env)

    def test_17_character_key_is_valid(self):
        """Una clave de 17 caracteres es válida."""
        env = {
            "ENVIRONMENT": "production",
            "API_KEYS": "client:12345678901234567",
            "MODEL_PROVIDER": "gateway",
            "CF_ACCOUNT_ID": "account-123",
            "CF_GATEWAY_ID": "gateway-123",
            "CF_API_TOKEN": "token-xyz",
        }

        settings = load_settings(env)
        assert settings is not None


class TestProductionEnvironmentDetection:
    """Pruebas para detección del ambiente de producción."""

    def test_development_by_default(self):
        """El ambiente por defecto es development."""
        env = {
            "MODEL_PROVIDER": "fake",
        }

        settings = load_settings(env)
        assert settings.environment == "development"

    def test_explicit_development_environment(self):
        """Ambiente explícitamente development."""
        env = {
            "ENVIRONMENT": "development",
            "MODEL_PROVIDER": "fake",
        }

        settings = load_settings(env)
        assert settings.environment == "development"

    def test_production_environment(self):
        """Ambiente production."""
        env = {
            "ENVIRONMENT": "production",
            "API_KEYS": "client:1234567890123456",
            "MODEL_PROVIDER": "gateway",
            "CF_ACCOUNT_ID": "account-123",
            "CF_GATEWAY_ID": "gateway-123",
            "CF_API_TOKEN": "token-xyz",
        }

        settings = load_settings(env)
        assert settings.environment == "production"

    def test_production_case_insensitive(self):
        """Detección de production no distingue mayúsculas."""
        env = {
            "ENVIRONMENT": "PRODUCTION",
            "API_KEYS": "client:1234567890123456",
            "MODEL_PROVIDER": "gateway",
            "CF_ACCOUNT_ID": "account-123",
            "CF_GATEWAY_ID": "gateway-123",
            "CF_API_TOKEN": "token-xyz",
        }

        settings = load_settings(env)
        assert settings.environment.lower() == "production"
