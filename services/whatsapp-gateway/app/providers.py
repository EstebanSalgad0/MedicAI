"""Proveedores de WhatsApp Business. Ambos usan el formato de mensajes de la Cloud API,
así que solo cambian la URL de envío y la autenticación.

  meta       WhatsApp Cloud API directa (graph.facebook.com)
  360dialog  Business Solution Provider: https://waba-v2.360dialog.io (header D360-API-KEY)

WHATSAPP_PROVIDER=auto elige 360dialog si existe D360_API_KEY y Meta si existe WHATSAPP_TOKEN.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Provider:
    name: str
    send_url: str
    headers: dict[str, str]
    configured: bool


def load() -> Provider:
    choice = os.getenv("WHATSAPP_PROVIDER", "auto").lower()
    d360_key = os.getenv("D360_API_KEY", "")
    meta_token = os.getenv("WHATSAPP_TOKEN", "")
    if choice == "auto":
        choice = "360dialog" if d360_key else "meta"

    if choice == "360dialog":
        base = os.getenv("D360_BASE_URL", "https://waba-v2.360dialog.io").rstrip("/")
        return Provider("360dialog", f"{base}/messages", {"D360-API-KEY": d360_key}, bool(d360_key))

    phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    version = os.getenv("WHATSAPP_API_VERSION", "v21.0")
    url = os.getenv("WHATSAPP_URL") or f"https://graph.facebook.com/{version}/{phone_id}/messages"
    return Provider("meta", url, {"Authorization": f"Bearer {meta_token}"},
                    bool(meta_token and (phone_id or os.getenv("WHATSAPP_URL"))))
