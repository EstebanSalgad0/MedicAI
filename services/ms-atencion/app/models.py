from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from medicai_common.service import Base, make_db

engine, SessionLocal = make_db("atencion.db")


class Ticket(Base):
    """Solicitud de contacto con una persona. Llega con el resumen de la conversación
    para que el funcionario no tenga que preguntar todo de nuevo."""

    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(120), index=True)
    channel: Mapped[str] = mapped_column(String(20), default="whatsapp")
    name: Mapped[str | None] = mapped_column(String(120))
    topic: Mapped[str] = mapped_column(String(30), index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    transcript: Mapped[list] = mapped_column(JSON, default=list)
    replies: Mapped[list] = mapped_column(JSON, default=list)
    acting_for: Mapped[str | None] = mapped_column(String(120))  # paciente, si lo pidió un cuidador
    in_hours: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(15), default="open", index=True)  # open | answered | closed
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Caregiver(Base):
    """Autorización para que un familiar gestione los trámites de un paciente."""

    __tablename__ = "caregivers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    caregiver_id: Mapped[str] = mapped_column(String(120), index=True)
    caregiver_name: Mapped[str] = mapped_column(String(120))
    caregiver_run: Mapped[str] = mapped_column(String(12))
    patient_name: Mapped[str] = mapped_column(String(120))
    patient_run: Mapped[str] = mapped_column(String(12), index=True)
    relationship: Mapped[str] = mapped_column(String(30))
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)


def init_db() -> None:
    Base.metadata.create_all(engine)
