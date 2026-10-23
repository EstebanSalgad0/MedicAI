from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from medicai_common.service import Base, make_db

engine, SessionLocal = make_db("derivacion.db")


class Referral(Base):
    """Trámite de derivación que el paciente pidió seguir (p. ej. una interconsulta)."""

    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    doc_type: Mapped[str] = mapped_column(String(20))  # interconsulta | examenes | receta | urgente | otro
    ges: Mapped[str | None] = mapped_column(String(5))  # si | no | ns
    status: Mapped[str] = mapped_column(String(15), default="open", index=True)  # open | contacted | closed
    followup_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    followup_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())



class Derivacion(Base):
    """Derivación clínica emitida por un profesional (Módulo 3), con trazabilidad hasta la
    atención de destino. Estados: enviada → agendada → atendida, o caducada."""

    __tablename__ = "derivaciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paciente_run: Mapped[str] = mapped_column(String(12), index=True)
    paciente_nombre: Mapped[str | None] = mapped_column(String(160))
    origen_id: Mapped[str] = mapped_column(String(40), index=True)
    destino_id: Mapped[str] = mapped_column(String(60), index=True)
    red: Mapped[str] = mapped_column(String(5))  # intra | extra
    especialidad: Mapped[str] = mapped_column(String(80))
    prioridad: Mapped[str] = mapped_column(String(12), default="normal")  # normal | preferente | urgente
    ges: Mapped[bool] = mapped_column(Boolean, default=False)
    motivo: Mapped[str] = mapped_column(String(500))
    responsable: Mapped[str] = mapped_column(String(160))
    estado: Mapped[str] = mapped_column(String(12), default="enviada", index=True)
    fecha_cita: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class DerivacionEvento(Base):
    """Cada cambio de estado: fecha, estado y responsable (trazabilidad completa)."""

    __tablename__ = "derivacion_eventos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    derivacion_id: Mapped[int] = mapped_column(ForeignKey("derivaciones.id"), index=True)
    estado: Mapped[str] = mapped_column(String(12))
    responsable: Mapped[str] = mapped_column(String(160))
    nota: Mapped[str | None] = mapped_column(String(500))
    at: Mapped[datetime] = mapped_column(DateTime)


def init_db() -> None:
    Base.metadata.create_all(engine)
