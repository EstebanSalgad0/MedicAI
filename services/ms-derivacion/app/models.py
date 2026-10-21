from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
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


def init_db() -> None:
    Base.metadata.create_all(engine)
