from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from medicai_common.service import Base, make_db

engine, SessionLocal = make_db("resultados.db")


class Patient(Base):
    """Identidad verificada de quien consulta (o del paciente, en modo cuidador)."""

    __tablename__ = "patients"

    user_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    run: Mapped[str] = mapped_column(String(12), index=True)
    birth_date: Mapped[date] = mapped_column(Date)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)


class ResultWatch(Base):
    """El paciente pidió aviso cuando un examen en proceso quede validado."""

    __tablename__ = "result_watches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(120), index=True)
    run: Mapped[str] = mapped_column(String(12))
    exam: Mapped[str] = mapped_column(String(80))
    ready_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


def init_db() -> None:
    Base.metadata.create_all(engine)
