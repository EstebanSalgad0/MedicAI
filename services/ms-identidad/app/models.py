from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from medicai_common.service import Base, make_db

engine, SessionLocal = make_db("identidad.db")


class Profesional(Base):
    """Funcionario habilitado para ingresar al dashboard con ClaveÚnica, con su rol y
    los establecimientos donde trabaja (base del control de permisos sobre pacientes)."""

    __tablename__ = "profesionales"

    run: Mapped[str] = mapped_column(String(12), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    rol: Mapped[str] = mapped_column(String(20))
    establecimientos: Mapped[list] = mapped_column(JSON, default=list)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Vinculo(Base):
    """Identidad del paciente verificada con ClaveÚnica, asociada a su número de WhatsApp.
    Así el chat nunca necesita pedirle el RUN ni otros datos de identidad."""

    __tablename__ = "vinculos"

    user_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    run: Mapped[str] = mapped_column(String(12), index=True)
    nombre: Mapped[str | None] = mapped_column(String(160))
    verified_at: Mapped[datetime] = mapped_column(DateTime)


class Solicitud(Base):
    """Enlace de un solo uso para ingresar con ClaveÚnica (vence en minutos).
    Su token viaja como `state` de OpenID Connect."""

    __tablename__ = "solicitudes"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    proposito: Mapped[str] = mapped_column(String(20))  # profesional | resultados | cuidador | derivacion | agenda
    user_id: Mapped[str | None] = mapped_column(String(120))
    destino: Mapped[str | None] = mapped_column(String(200))  # a dónde volver (dashboard)
    run: Mapped[str | None] = mapped_column(String(12))  # identidad ya verificada (paso 2 del cuidador)
    nombre: Mapped[str | None] = mapped_column(String(160))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


def init_db() -> None:
    Base.metadata.create_all(engine)
