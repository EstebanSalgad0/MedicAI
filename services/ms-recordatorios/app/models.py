from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from medicai_common.service import Base, ensure_columns, make_db

engine, SessionLocal = make_db("recordatorios.db")


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    medication: Mapped[str] = mapped_column(String(120))
    times: Mapped[str] = mapped_column(String(120))  # "08:00,20:00"
    dose: Mapped[str | None] = mapped_column(String(60))          # "1 comprimido"
    rx_end: Mapped[date | None] = mapped_column(Date)            # fin de la receta (aviso de renovación)
    rx_notified: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    source: Mapped[str] = mapped_column(String(20), default="chat")  # chat | medicamentos | derivacion
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    @property
    def time_list(self) -> list[str]:
        return [t for t in self.times.split(",") if t]


class DoseLog(Base):
    """Una toma programada. Su estado alimenta el indicador de adherencia."""

    __tablename__ = "dose_logs"
    __table_args__ = (UniqueConstraint("reminder_id", "scheduled_date", "slot"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reminder_id: Mapped[int] = mapped_column(ForeignKey("reminders.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    scheduled_date: Mapped[date] = mapped_column(Date, index=True)
    slot: Mapped[str] = mapped_column(String(5))
    # sent | snoozed | taken | skipped | expired
    status: Mapped[str] = mapped_column(String(10), default="sent", index=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime)
    snooze_until: Mapped[datetime | None] = mapped_column(DateTime)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime)


def init_db() -> None:
    Base.metadata.create_all(engine)
    ensure_columns(engine, "reminders", {"dose": "VARCHAR(60)", "rx_end": "DATE", "rx_notified": "BOOLEAN DEFAULT FALSE"})
