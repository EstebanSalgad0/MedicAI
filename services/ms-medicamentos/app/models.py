from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from medicai_common.service import Base, make_db

engine, SessionLocal = make_db("medicamentos.db")


class StockItem(Base):
    __tablename__ = "stock"
    __table_args__ = (UniqueConstraint("center_id", "key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    center_id: Mapped[str] = mapped_column(String(40), index=True)
    key: Mapped[str] = mapped_column(String(120), index=True)  # nombre normalizado
    name: Mapped[str] = mapped_column(String(120))
    stock: Mapped[int] = mapped_column(Integer, default=0)
    min_stock: Mapped[int] = mapped_column(Integer, default=10)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Pickup(Base):
    """Retiro programado en la farmacia del CESFAM (único o cíclico)."""

    __tablename__ = "pickups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    medication: Mapped[str] = mapped_column(String(120))
    center_id: Mapped[str | None] = mapped_column(String(40), index=True)
    due_date: Mapped[date] = mapped_column(Date, index=True)
    hour: Mapped[str] = mapped_column(String(5), default="09:00")
    freq_days: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10), default="pending", index=True)  # pending | done | missed
    notified_before: Mapped[bool] = mapped_column(Boolean, default=False)
    notified_day: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class StockAlert(Base):
    """Paciente que pidió aviso cuando vuelva a haber stock."""

    __tablename__ = "stock_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64))
    center_id: Mapped[str] = mapped_column(String(40))
    key: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(120))
    notified: Mapped[bool] = mapped_column(Boolean, default=False)


def init_db() -> None:
    Base.metadata.create_all(engine)
