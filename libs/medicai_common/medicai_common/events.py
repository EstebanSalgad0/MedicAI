"""Emisión de eventos de telemetría al servicio de analítica.

Es fire-and-forget: si analítica no responde, el servicio de dominio sigue
funcionando y el evento se registra en el log.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Any

import httpx

ANALYTICS_URL = os.getenv("ANALYTICS_URL", "http://analytics:8000")
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "")
log = logging.getLogger("medicai.events")


def _post(payload: dict[str, Any]) -> None:
    try:
        httpx.post(
            f"{ANALYTICS_URL}/internal/events",
            json=payload,
            headers={"X-Internal-Token": INTERNAL_TOKEN},
            timeout=2.0,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("No se pudo enviar evento %s: %s", payload.get("type"), exc)


def emit(
    event_type: str,
    *,
    service: str,
    user_id: str | None = None,
    channel: str | None = None,
    center: str | None = None,
    props: dict[str, Any] | None = None,
    blocking: bool = False,
) -> None:
    payload = {
        "events": [
            {
                "type": event_type,
                "service": service,
                "user_id": user_id,
                "channel": channel,
                "center": center,
                "props": props or {},
            }
        ]
    }
    if blocking:
        _post(payload)
    else:
        threading.Thread(target=_post, args=(payload,), daemon=True).start()
