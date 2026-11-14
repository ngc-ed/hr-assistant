"""Pruebas unitarias para validación de API Key en autenticación."""

import pytest
from fastapi import HTTPException

from app.auth import extract_api_key_from_header, parse_api_keys, validate_api_key


class TestParseApiKeys:
    """Pruebas para el parser de API_KEYS."""

    def test_parse_single_api_key_pair(self):
        """Parsear un par cliente:clave."""
        api_keys_str = "client1:secretkey123456"
        result = parse_api_keys(api_keys_str)
        assert result == {"client1": "secretkey123456"}

    def test_parse_multiple_api_key_pairs(self):
        """Parsear múltiples pares cliente:clave."""
        api_keys_str = "alice:secretkey123456,bob:anothersecret789"
        result = parse_api_keys(api_keys_str)
        assert result == {
            "alice": "secretkey123456",
            "bob": "anothersecret789",
        }

    def test_parse_empty_string(self):
        """Parsear una cadena vacía devuelve diccionario vacío."""
        result = parse_api_keys("")
        assert not result

    def test_parse_invalid_format_missing_colon(self):
        """Parsear un formato inválido sin colon falla."""
        api_keys_str = "clientonlyname"
        with pytest.raises(ValueError):
            parse_api_keys(api_keys_str)

    def test_parse_invalid_format_missing_value(self):
        """Parsear un formato con colon pero sin valor falla."""
        api_keys_str = "client:"
        with pytest.raises(ValueError):
            parse_api_keys(api_keys_str)

    def test_parse_invalid_format_empty_client_name(self):
        """Parsear un formato con cliente vacío falla."""
        api_keys_str = ":secretkey123456"
        with pytest.raises(ValueError):
            parse_api_keys(api_keys_str)

    def test_parse_error_message_excludes_key_value(self):
        """El mensaje de error nunca muestra el valor de la clave."""
        api_keys_str = "invalid_entry"
        with pytest.raises(ValueError) as exc_info:
            parse_api_keys(api_keys_str)

        error_message = str(exc_info.value)
        assert "invalid_entry" not in error_message


class TestExtractApiKeyFromHeader:
    """Pruebas para extracción del encabezado X-API-Key."""

    def test_extract_valid_api_key_from_header(self):
        """Extraer una clave válida del encabezado."""
        headers = {"X-API-Key": "secretkey123456"}
        result = extract_api_key_from_header(headers)
        assert result == "secretkey123456"

    def test_extract_api_key_missing_header(self):
        """Extraer sin el encabezado devuelve None."""
        headers = {}
        result = extract_api_key_from_header(headers)
        assert result is None

    def test_extract_api_key_case_insensitive(self):
        """La búsqueda del encabezado no distingue mayúsculas."""
        headers = {"x-api-key": "secretkey123456"}
        result = extract_api_key_from_header(headers)
        assert result == "secretkey123456"

    def test_extract_api_key_with_other_headers(self):
        """Extraer la clave entre otros encabezados."""
        headers = {
            "User-Agent": "test-client",
            "X-API-Key": "secretkey123456",
            "Content-Type": "application/json",
        }
        result = extract_api_key_from_header(headers)
        assert result == "secretkey123456"


class TestValidateApiKey:
    """Pruebas para validación de API Key."""

    def test_validate_valid_api_key(self):
        """Validar una clave válida devuelve el cliente."""
        api_keys = {
            "alice": "secretkey123456",
            "bob": "anothersecret789",
        }
        result = validate_api_key("secretkey123456", api_keys)
        assert result == "alice"

    def test_validate_invalid_api_key(self):
        """Validar una clave inválida falla."""
        api_keys = {
            "alice": "secretkey123456",
            "bob": "anothersecret789",
        }
        with pytest.raises(HTTPException) as exc_info:
            validate_api_key("wrongkey", api_keys)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "invalid or missing API key"

    def test_validate_empty_api_key(self):
        """Validar una clave vacía falla."""
        api_keys = {
            "alice": "secretkey123456",
        }
        with pytest.raises(HTTPException) as exc_info:
            validate_api_key("", api_keys)

        assert exc_info.value.status_code == 401

    def test_validate_none_api_key(self):
        """Validar None como clave falla."""
        api_keys = {
            "alice": "secretkey123456",
        }
        with pytest.raises(HTTPException) as exc_info:
            validate_api_key(None, api_keys)

        assert exc_info.value.status_code == 401

    def test_validate_error_does_not_expose_key(self):
        """El error nunca expone la clave intentada."""
        api_keys = {
            "alice": "secretkey123456",
        }
        with pytest.raises(HTTPException) as exc_info:
            validate_api_key("wrongkey", api_keys)

        error_detail = str(exc_info.value.detail)
        assert "wrongkey" not in error_detail
        assert "secretkey123456" not in error_detail

    def test_validate_api_key_case_sensitive(self):
        """Validar que las claves distinguen mayúsculas."""
        api_keys = {
            "alice": "SecretKey123456",
        }
        with pytest.raises(HTTPException):
            validate_api_key("secretkey123456", api_keys)

    def test_validate_multiple_clients_returns_correct_client(self):
        """Validar con múltiples clientes devuelve el cliente correcto."""
        api_keys = {
            "alice": "alice-secretkey123456",
            "bob": "bob-anothersecret789",
            "charlie": "charlie-thirdkey12345",
        }

        assert validate_api_key("alice-secretkey123456", api_keys) == "alice"
        assert validate_api_key("bob-anothersecret789", api_keys) == "bob"
        assert validate_api_key("charlie-thirdkey12345", api_keys) == "charlie"


class TestApiKeyValidationIntegration:
    """Pruebas de integración para validación de API Key."""

    def test_full_flow_parse_and_validate(self):
        """Flujo completo: parsear API_KEYS y validar una clave."""
        api_keys_str = "alice:secretkey123456,bob:anothersecret789"
        api_keys = parse_api_keys(api_keys_str)

        headers = {"X-API-Key": "secretkey123456"}
        api_key = extract_api_key_from_header(headers)

        client = validate_api_key(api_key, api_keys)
        assert client == "alice"

    def test_full_flow_with_missing_header(self):
        """Flujo completo con encabezado faltante."""
        api_keys_str = "alice:secretkey123456"
        api_keys = parse_api_keys(api_keys_str)

        headers = {}
        api_key = extract_api_key_from_header(headers)

        with pytest.raises(HTTPException) as exc_info:
            validate_api_key(api_key, api_keys)

        assert exc_info.value.status_code == 401

    def test_full_flow_with_invalid_key(self):
        """Flujo completo con clave inválida."""
        api_keys_str = "alice:secretkey123456"
        api_keys = parse_api_keys(api_keys_str)

        headers = {"X-API-Key": "wrongkey"}
        api_key = extract_api_key_from_header(headers)

        with pytest.raises(HTTPException) as exc_info:
            validate_api_key(api_key, api_keys)

        assert exc_info.value.status_code == 401
        assert "invalid or missing API key" in exc_info.value.detail
