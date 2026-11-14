"""Autenticación por API Key: validación de clientes y extracción de nombres."""

import hmac
from typing import Mapping

from fastapi import HTTPException


def parse_api_keys(api_keys_str: str) -> dict[str, str]:
    """Parsea el formato ``cliente:clave,cliente2:clave2``.

    :param api_keys_str: Cadena con pares cliente:clave separados por comas
    :type api_keys_str: str
    :return: Diccionario {cliente: clave}
    :rtype: dict[str, str]
    :raises ValueError: Si el formato es inválido (nunca expone valores)
    """
    if not api_keys_str or not api_keys_str.strip():
        return {}

    result = {}
    for i, pair in enumerate(api_keys_str.split(",")):
        pair = pair.strip()
        if not pair:
            continue

        if ":" not in pair:
            raise ValueError(
                f"API_KEYS entry {i} (length {len(pair)}) has invalid format: "
                "expected 'client:key'"
            )

        parts = pair.split(":", 1)
        client, key = parts[0].strip(), parts[1].strip()

        if not client:
            raise ValueError(
                f"API_KEYS entry {i}: client name cannot be empty"
            )
        if not key:
            raise ValueError(
                f"API_KEYS entry {i}: key for client {client!r} cannot be empty"
            )

        result[client] = key

    return result


def extract_api_key_from_header(headers: Mapping[str, str]) -> str | None:
    """Extrae la clave del encabezado X-API-Key (case-insensitive).

    :param headers: Diccionario de encabezados
    :type headers: Mapping[str, str]
    :return: La clave si está presente, None si no
    :rtype: str | None
    """
    # Buscar case-insensitive
    for key, value in headers.items():
        if key.lower() == "x-api-key":
            return value
    return None


def validate_api_key(
    api_key: str | None, api_keys: dict[str, str]
) -> str:
    """Valida una clave contra el diccionario y devuelve el cliente.

    Usa ``hmac.compare_digest`` para evitar ataques de tiempo. La clave
    nunca se escribe en errores.

    :param api_key: La clave a validar (puede ser None)
    :type api_key: str | None
    :param api_keys: Diccionario {cliente: clave}
    :type api_keys: dict[str, str]
    :return: El nombre del cliente si la clave es válida
    :rtype: str
    :raises HTTPException: 401 si la clave no es válida o falta
    """
    if not api_key:
        raise HTTPException(
            status_code=401, detail="invalid or missing API key"
        )

    for client, stored_key in api_keys.items():
        if hmac.compare_digest(api_key, stored_key):
            return client

    raise HTTPException(
        status_code=401, detail="invalid or missing API key"
    )
