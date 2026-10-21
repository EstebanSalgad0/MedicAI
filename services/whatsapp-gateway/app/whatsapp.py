"""Traducción de mensajes de MedicAI al formato de WhatsApp Cloud API, respetando sus límites."""
from __future__ import annotations

from typing import Any

from medicai_common.messages import Message

LIM = {"text": 4096, "interactive_body": 1024, "footer": 60, "button_title": 20, "row_title": 24,
       "row_desc": 72, "list_button": 20, "max_buttons": 3, "max_rows": 10}


def _cut(s: str | None, n: int) -> str:
    s = s or ""
    return s if len(s) <= n else s[: n - 1] + "…"


def to_payloads(to: str, m: Message) -> list[dict[str, Any]]:
    base = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to}
    if m.type == "text" or not m.options:
        chunks = [m.text[i:i + LIM["text"]] for i in range(0, len(m.text), LIM["text"])] or [""]
        return [{**base, "type": "text", "text": {"body": c, "preview_url": False}} for c in chunks]

    payloads: list[dict[str, Any]] = []
    body = m.text
    if len(body) > LIM["interactive_body"]:
        # el cuerpo largo va como texto y el interactivo lleva solo la pregunta
        payloads.append({**base, "type": "text", "text": {"body": _cut(body, LIM["text"])}})
        body = "Elige una opción:"
    interactive: dict[str, Any] = {"body": {"text": body}}
    if m.footer:
        interactive["footer"] = {"text": _cut(m.footer, LIM["footer"])}
    if m.type == "buttons" and len(m.options) <= LIM["max_buttons"]:
        interactive["type"] = "button"
        interactive["action"] = {"buttons": [
            {"type": "reply", "reply": {"id": o.id, "title": _cut(o.title, LIM["button_title"])}} for o in m.options]}
    else:
        interactive["type"] = "list"
        rows = []
        for o in m.options[: LIM["max_rows"]]:
            row = {"id": o.id, "title": _cut(o.title, LIM["row_title"])}
            desc = o.description or (o.title if len(o.title) > LIM["row_title"] else None)
            if desc:
                row["description"] = _cut(desc, LIM["row_desc"])
            rows.append(row)
        interactive["action"] = {"button": _cut(m.button or "Ver opciones", LIM["list_button"]),
                                 "sections": [{"title": "Opciones", "rows": rows}]}
    payloads.append({**base, "type": "interactive", "interactive": interactive})
    return payloads


def parse_inbound(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Extrae los mensajes de un webhook (puede traer varios, o solo estados de entrega)."""
    out = []
    if "messages" in body and "entry" not in body:
        # formato plano (On-Premise / algunos BSP): se normaliza a la estructura de la Cloud API
        body = {"entry": [{"changes": [{"value": body}]}]}
    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            names = {c.get("wa_id"): c.get("profile", {}).get("name") for c in value.get("contacts", [])}
            for m in value.get("messages", []):
                item = {"id": m.get("id"), "from": m.get("from"), "name": names.get(m.get("from")),
                        "text": "", "option_id": None, "media": None}
                t = m.get("type")
                if t == "text":
                    item["text"] = m["text"].get("body", "")
                elif t == "interactive":
                    inter = m["interactive"]
                    reply = inter.get(inter.get("type"), {})
                    item["option_id"], item["text"] = reply.get("id"), reply.get("title", "")
                elif t == "button":  # respuesta rápida de una plantilla
                    item["option_id"] = m["button"].get("payload") or None
                    item["text"] = m["button"].get("text", "")
                else:
                    item["media"] = t
                out.append(item)
    return out
