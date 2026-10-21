"""Registra en 360dialog la URL del webhook de MedicAI.

Uso (con los contenedores levantados):
    docker compose exec whatsapp-gateway python -m app.register_webhook https://<dominio>/webhook

Usa D360_API_KEY del .env y, si existe WEBHOOK_SECRET, pide a 360dialog enviarlo como
header en cada notificación para que el gateway pueda verificar el origen.
"""
from __future__ import annotations

import os
import sys

import httpx

from .main import WEBHOOK_SECRET, WEBHOOK_SECRET_HEADER


def main() -> int:
    if len(sys.argv) != 2 or not sys.argv[1].startswith("https://"):
        print("Uso: python -m app.register_webhook https://<dominio-publico>/webhook  (debe ser HTTPS)")
        return 2
    key = os.getenv("D360_API_KEY")
    if not key:
        print("Falta D360_API_KEY en el .env")
        return 2
    base = os.getenv("D360_BASE_URL", "https://waba-v2.360dialog.io").rstrip("/")
    body = {"url": sys.argv[1], "headers": {WEBHOOK_SECRET_HEADER: WEBHOOK_SECRET} if WEBHOOK_SECRET else {}}
    r = httpx.post(f"{base}/v1/configs/webhook", json=body, headers={"D360-API-KEY": key}, timeout=20)
    print(r.status_code, r.text)
    if r.is_success:
        print("✔ Webhook registrado." + ("" if WEBHOOK_SECRET else
              " Aviso: sin WEBHOOK_SECRET el gateway no puede verificar el origen de los mensajes."))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
