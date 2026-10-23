"""Mensajes independientes del canal.

Los microservicios responden con estos objetos; el gateway de WhatsApp los
traduce a la API de Meta y el simulador web los muestra tal cual. Así ningún
servicio de dominio depende de WhatsApp.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Option(BaseModel):
    """Opción seleccionable. El `id` lleva el prefijo del servicio dueño
    (agd:, rec:, ori:, der:, med:, sys:) para que el orquestador enrute la
    respuesta sin pasar por el NLU."""

    id: str
    title: str
    description: str | None = None


class Message(BaseModel):
    type: Literal["text", "buttons", "list"] = "text"
    text: str
    footer: str | None = None
    button: str | None = None  # rótulo del botón que abre una lista
    options: list[Option] = Field(default_factory=list)


def text(body: str) -> Message:
    return Message(type="text", text=body)


def buttons(body: str, options: list[tuple[str, str]], footer: str | None = None) -> Message:
    """Hasta 3 botones (límite de WhatsApp)."""
    return Message(
        type="buttons",
        text=body,
        footer=footer,
        options=[Option(id=i, title=t) for i, t in options[:3]],
    )


def lst(
    body: str,
    options: list[tuple[str, str] | tuple[str, str, str]],
    footer: str | None = None,
    button: str = "Ver opciones",
) -> Message:
    """Lista desplegable, hasta 10 filas (límite de WhatsApp)."""
    opts = []
    for o in options[:10]:
        opts.append(Option(id=o[0], title=o[1], description=o[2] if len(o) > 2 else None))
    return Message(type="list", text=body, footer=footer, button=button, options=opts)


DISCLAIMER = "\n\n_MedicAI no entrega diagnósticos ni recetas. Ante una emergencia llama al SAMU 131._"
