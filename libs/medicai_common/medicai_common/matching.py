"""Permite responder a una lista o botones escribiendo en vez de tocar la opción.

Los servicios guardan en su estado el último menú enviado (`_menu`); si el
usuario escribe "2" o "odontología", se traduce al id de la opción.
"""
from __future__ import annotations

from typing import Any

from .contracts import DialogRequest
from .messages import Message
from .textutil import normalize


def match_option(text: str, message: Message | None) -> str | None:
    if not message or not text:
        return None
    t = normalize(text)
    if t.isdigit():  # "2" -> segunda opción
        idx = int(t) - 1
        if 0 <= idx < len(message.options):
            return message.options[idx].id
    if len(t) < 2:
        return None
    for opt in message.options:
        title = normalize("".join(ch for ch in opt.title if ch.isalnum() or ch.isspace())).strip()
        if title and (title == t or (len(t) >= 4 and (t in title or title in t))):
            return opt.id
    return None


def choice(req: DialogRequest) -> str | None:
    """Id de opción elegido: el que viene del botón o el inferido del texto."""
    if req.option_id:
        return req.option_id
    menu = req.state.get("_menu")
    return match_option(req.text, Message(**menu)) if menu else None


def remember_menu(state: dict[str, Any], msg: Message) -> dict[str, Any]:
    state = dict(state)
    state["_menu"] = msg.model_dump()
    return state
