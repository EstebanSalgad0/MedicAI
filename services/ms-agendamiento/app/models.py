from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from medicai_common.service import Base, make_db

engine, SessionLocal = make_db("agendamiento.db")


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    patient_name: Mapped[str | None] = mapped_column(String(120))
    channel: Mapped[str] = mapped_column(String(20), default="whatsapp")
    prestacion: Mapped[str] = mapped_column(String(40))
    center_id: Mapped[str] = mapped_column(String(40), index=True)
    slot_at: Mapped[datetime] = mapped_column(DateTime, index=True)  # hora local Chile
    # confirmed | cancelled | attended | no_show
    status: Mapped[str] = mapped_column(String(20), default="confirmed", index=True)
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    attendance_reply: Mapped[str | None] = mapped_column(String(20))  # yes | reschedule | cancel
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


def init_db() -> None:
    Base.metadata.create_all(engine)
