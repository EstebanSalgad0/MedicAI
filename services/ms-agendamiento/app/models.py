from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from medicai_common.service import Base, ensure_columns, make_db

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
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False)       # recordatorio de 24 h
    reminder_48_sent: Mapped[bool] = mapped_column(Boolean, default=False)    # recordatorio de 48 h
    attendance_reply: Mapped[str | None] = mapped_column(String(20))  # yes | reschedule | cancel
    ges: Mapped[str | None] = mapped_column(String(60))  # problema GES mencionado por el paciente
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    @property
    def code(self) -> str:
        """Código de reserva que se le entrega al paciente (HRT-000123 en el hospital)."""
        return f"{'HRT' if self.center_id == 'hrt' else 'APS'}-{self.id:06d}"


class Waitlist(Base):
    """Lista de espera: pacientes sin hora disponible o que quieren una hora antes
    (en ese caso `appointment_id` es la hora que ya tienen)."""

    __tablename__ = "waitlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    patient_name: Mapped[str | None] = mapped_column(String(120))
    channel: Mapped[str] = mapped_column(String(20), default="whatsapp")
    center_id: Mapped[str] = mapped_column(String(40), index=True)
    prestacion: Mapped[str] = mapped_column(String(40), index=True)
    appointment_id: Mapped[int | None] = mapped_column(ForeignKey("appointments.id"))
    priority: Mapped[int] = mapped_column(Integer, default=0)  # 0 orden de llegada · 1 GES · 2 prioridad clínica
    priority_reason: Mapped[str | None] = mapped_column(String(200))  # motivo clínico registrado por el equipo
    priority_by: Mapped[str | None] = mapped_column(String(160))  # responsable que asignó la prioridad
    status: Mapped[str] = mapped_column(String(15), default="waiting", index=True)  # waiting | booked | cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class GapOffer(Base):
    """Fill-the-gap: cada oferta de un cupo liberado queda registrada (auditable)."""

    __tablename__ = "gap_offers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    waitlist_id: Mapped[int] = mapped_column(ForeignKey("waitlist.id"), index=True)
    slot_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    center_id: Mapped[str] = mapped_column(String(40))
    prestacion: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(15), default="offered", index=True)  # offered|accepted|declined|expired|taken
    offered_at: Mapped[datetime] = mapped_column(DateTime)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime)
    criterio: Mapped[str | None] = mapped_column(String(300))  # por qué se ofreció a este paciente


def init_db() -> None:
    Base.metadata.create_all(engine)
    ensure_columns(engine, "appointments", {"reminder_48_sent": "BOOLEAN DEFAULT FALSE", "ges": "VARCHAR(60)"})
    ensure_columns(engine, "waitlist", {"priority_reason": "VARCHAR(200)", "priority_by": "VARCHAR(160)"})
    ensure_columns(engine, "gap_offers", {"criterio": "VARCHAR(300)"})
