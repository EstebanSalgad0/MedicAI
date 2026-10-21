"""Contrato de diálogo entre el orquestador y los microservicios de dominio.

Cada microservicio expone `POST /dialog`. El orquestador le entrega el mensaje
del usuario ya interpretado por el NLU junto con el estado de sesión que el
propio servicio devolvió en el turno anterior, y recibe mensajes, nuevo estado
y eventos de dominio. El servicio no guarda sesiones: es stateless respecto de
la conversación, lo que permite escalarlo horizontalmente.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .messages import Message


class DialogRequest(BaseModel):
    user_id: str
    channel: str = "whatsapp"
    name: str | None = None
    text: str = ""
    option_id: str | None = None
    intent: str | None = None
    entities: dict[str, Any] = Field(default_factory=dict)
    state: dict[str, Any] = Field(default_factory=dict)
    start: bool = False  # True cuando el orquestador inicia el flujo desde cero


class DomainEvent(BaseModel):
    type: str
    props: dict[str, Any] = Field(default_factory=dict)
    center: str | None = None


class Handoff(BaseModel):
    """Pide al orquestador iniciar otro servicio (p. ej. medicamentos -> recordatorios)."""

    service: str
    intent: str | None = None
    entities: dict[str, Any] = Field(default_factory=dict)


class DialogResponse(BaseModel):
    messages: list[Message] = Field(default_factory=list)
    state: dict[str, Any] | None = None  # None = el flujo terminó
    resolved: bool = False  # el usuario completó su trámite sin intervención humana
    events: list[DomainEvent] = Field(default_factory=list)
    handoff: Handoff | None = None
    # Modo cuidador: {"id": ..., "name": ...} hace que el orquestador atienda los trámites
    # siguientes a nombre de esa persona; {} vuelve a la cuenta propia; None no cambia nada.
    acting: dict[str, str] | None = None


def reply(*messages: Message, state: dict | None = None, resolved: bool = False,
          events: list[DomainEvent] | None = None, handoff: Handoff | None = None,
          acting: dict[str, str] | None = None) -> DialogResponse:
    return DialogResponse(
        messages=list(messages),
        state=state,
        resolved=resolved,
        events=events or [],
        handoff=handoff,
        acting=acting,
    )
