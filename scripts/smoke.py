#!/usr/bin/env python3
"""
Prueba de humo para validar el despliegue en Render.
Lee la clave de la variable de entorno SMOKE_API_KEY y comprueba:
- /health responde 200
- /ask sin clave responde 401
- /ask con clave responde 200
"""

import os
import sys
import httpx


def main():
    if len(sys.argv) != 2:
        print("Uso: python smoke.py <url>")
        sys.exit(1)

    base_url = sys.argv[1].rstrip("/")
    api_key = os.environ.get("SMOKE_API_KEY")

    if not api_key:
        print("[FAIL] Variable SMOKE_API_KEY no definida")
        sys.exit(1)

    client = httpx.Client(timeout=10)
    failed = False

    try:
        # Prueba 1: /health debe responder 200
        print("Comprobando /health...", end=" ")
        response = client.get(f"{base_url}/health")
        if response.status_code == 200:
            print("[OK]")
        else:
            print(f"[FAIL] (status: {response.status_code})")
            failed = True

        # Prueba 2: /ask sin clave debe responder 401
        print("Comprobando /ask sin clave...", end=" ")
        response = client.post(
            f"{base_url}/ask",
            json={"question": "test", "history": []}
        )
        if response.status_code == 401:
            print("[OK]")
        else:
            print(f"[FAIL] (status: {response.status_code})")
            failed = True

        # Prueba 3: /ask con clave debe responder 200
        print("Comprobando /ask con clave...", end=" ")
        response = client.post(
            f"{base_url}/ask",
            json={"question": "test", "history": []},
            headers={"X-API-Key": api_key}
        )
        if response.status_code == 200:
            print("[OK]")
        else:
            print(f"[FAIL] (status: {response.status_code})")
            failed = True

    finally:
        client.close()

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
