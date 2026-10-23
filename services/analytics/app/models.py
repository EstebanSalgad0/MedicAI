from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from medicai_common.service import Base, make_db

engine, SessionLocal = make_db("analytics.db")


class Event(Base):
    """Evento de telemetría seudonimizado (no guarda teléfonos ni texto de los mensajes)."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)  # UTC
    type: Mapped[str] = mapped_column(String(40), index=True)
    service: Mapped[str] = mapped_column(String(30), index=True)
    user_hash: Mapped[str | None] = mapped_column(String(16), index=True)
    channel: Mapped[str | None] = mapped_column(String(15), index=True)
    center: Mapped[str | None] = mapped_column(String(40), index=True)
    props: Mapped[dict] = mapped_column(JSON, default=dict)


def init_db() -> None:
    Base.metadata.create_all(engine)
