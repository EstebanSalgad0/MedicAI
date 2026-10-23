from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from medicai_common.service import Base, make_db

engine, SessionLocal = make_db("historial.db")


class Ficha(Base):
    """Registro clínico estructurado desde el dictado. Mientras es borrador lo edita su autor;
    una vez firmado no se modifica."""

    __tablename__ = "fichas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paciente_run: Mapped[str] = mapped_column(String(12), index=True)
    establecimiento_id: Mapped[str] = mapped_column(String(40))
    profesional_run: Mapped[str] = mapped_column(String(12), index=True)
    profesional_nombre: Mapped[str] = mapped_column(String(160))
    transcripcion: Mapped[str] = mapped_column(Text, default="")
    secciones: Mapped[list] = mapped_column(JSON, default=list)
    origen: Mapped[str] = mapped_column(String(80), default="reglas")
    estado: Mapped[str] = mapped_column(String(12), default="borrador", index=True)  # borrador | firmada
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    firmada_at: Mapped[datetime | None] = mapped_column(DateTime)


class Acceso(Base):
    """Auditoría de cada consulta a la ficha de un paciente (Ley 20.584: acceso solo de quienes
    participan en su atención). Registra también los accesos denegados."""

    __tablename__ = "accesos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    profesional_run: Mapped[str | None] = mapped_column(String(12), index=True)
    profesional_nombre: Mapped[str] = mapped_column(String(160))
    rol: Mapped[str] = mapped_column(String(20))
    paciente_run: Mapped[str] = mapped_column(String(12), index=True)
    establecimientos: Mapped[list] = mapped_column(JSON, default=list)
    accion: Mapped[str] = mapped_column(String(20))  # perfil | apoyo | ficha
    motivo: Mapped[str] = mapped_column(String(20))
    resultado: Mapped[str] = mapped_column(String(40))  # permitido | denegado | excepcional_urgencia
    detalle: Mapped[str | None] = mapped_column(String(200))


def init_db() -> None:
    Base.metadata.create_all(engine)
