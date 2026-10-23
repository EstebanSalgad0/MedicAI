"""Envío de mensajes proactivos (recordatorios) a través del gateway de canales."""
from __future__ import annotations

import logging
import os

import httpx

from .messages import Message

GATEWAY_URL = os.getenv("WHATSAPP_GATEWAY_URL", "http://whatsapp-gateway:8000")
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "")
log = logging.getLogger("medicai.notify")


def send(user_id: str, messages: list[Message]) -> bool:
    try:
        r = httpx.post(
            f"{GATEWAY_URL}/internal/send",
            json={"to": user_id, "messages": [m.model_dump() for m in messages]},
            headers={"X-Internal-Token": INTERNAL_TOKEN},
            timeout=10.0,
        )
        r.raise_for_status()
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("Fallo al enviar notificación a %s: %s", user_id, exc)
        return False
