from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from medicai_common import events
from medicai_common.contracts import DialogRequest, DialogResponse
from medicai_common.messages import buttons
from medicai_common.notify import send
from medicai_common.service import create_service, require_internal, setup_logging
from medicai_common.textutil import now_local

from . import dialog
from .catalog import CENTRO_NOMBRE, CENTROS, PRESTACION_NOMBRE, PRESTACIONES
from .models import Appointment, SessionLocal, init_db

SERVICE = "agendamiento"
log = setup_logging(SERVICE)
app = create_service(SERVICE, "Reserva, reagendamiento y cancelación de horas en CESFAM, "
                              "con recordatorio de asistencia el día anterior.", on_startup=init_db)


@app.post("/dialog", response_model=DialogResponse, dependencies=[Depends(require_internal)], tags=["chat"])
def post_dialog(req: DialogRequest) -> DialogResponse:
    return dialog.handle(req)


# ---------- API para el dashboard (funcionarios) ----------

class AppointmentOut(BaseModel):
    id: int
    patient_name: str | None
    prestacion: str
    prestacion_nombre: str
    center_id: str
    center_nombre: str
    slot_at: datetime
    status: str
    attendance_reply: str | None
    channel: str


def _out(a: Appointment) -> AppointmentOut:
    return AppointmentOut(
        id=a.id, patient_name=a.patient_name, prestacion=a.prestacion,
        prestacion_nombre=PRESTACION_NOMBRE.get(a.prestacion, a.prestacion), center_id=a.center_id,
        center_nombre=CENTRO_NOMBRE.get(a.center_id, a.center_id), slot_at=a.slot_at,
        status=a.status, attendance_reply=a.attendance_reply, channel=a.channel,
    )


@app.get("/catalog", tags=["dashboard"])
def catalog():
    return {
        "centers": [{"id": k, "nombre": n, "comuna": c} for k, n, c in CENTROS],
        "prestaciones": [{"id": k, "nombre": PRESTACION_NOMBRE[k]} for k, _ in PRESTACIONES],
    }


@app.get("/appointments", response_model=list[AppointmentOut], tags=["dashboard"])
def list_appointments(center_id: str | None = None, status: str | None = None,
                      date_from: date | None = None, date_to: date | None = None, limit: int = 200):
    q = select(Appointment)
    if center_id:
        q = q.where(Appointment.center_id == center_id)
    if status:
        q = q.where(Appointment.status == status)
    if date_from:
        q = q.where(Appointment.slot_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        q = q.where(Appointment.slot_at < datetime.combine(date_to + timedelta(days=1), datetime.min.time()))
    with SessionLocal() as db:
        return [_out(a) for a in db.scalars(q.order_by(Appointment.slot_at).limit(min(limit, 1000)))]


class StatusUpdate(BaseModel):
    status: Literal["attended", "no_show", "cancelled", "confirmed"]


@app.patch("/appointments/{appt_id}", response_model=AppointmentOut, tags=["dashboard"])
def update_status(appt_id: int, body: StatusUpdate):
    """El funcionario registra asistencia o inasistencia: base del indicador de inasistencia."""
    with SessionLocal() as db:
        a = db.get(Appointment, appt_id)
        if not a:
            raise HTTPException(404, "Cita no encontrada")
        a.status = body.status
        db.commit()
        out = _out(a)
    if body.status in ("attended", "no_show"):
        events.emit(f"appointment_{body.status}", service=SERVICE, user_id=a.user_id, center=a.center_id,
                    props={"appointment_id": a.id, "attendance_reply": a.attendance_reply,
                           "prestacion": a.prestacion})
    return out


@app.get("/stats", tags=["dashboard"])
def stats():
    with SessionLocal() as db:
        by_status = dict(db.execute(select(Appointment.status, func.count()).group_by(Appointment.status)).all())
        by_center = [
            {"center_id": c, "center_nombre": CENTRO_NOMBRE.get(c, c), "status": s, "total": n}
            for c, s, n in db.execute(select(Appointment.center_id, Appointment.status, func.count())
                                      .group_by(Appointment.center_id, Appointment.status)).all()
        ]
    closed = by_status.get("attended", 0) + by_status.get("no_show", 0)
    return {
        "by_status": by_status,
        "by_center": by_center,
        "no_show_rate": round(by_status.get("no_show", 0) / closed, 4) if closed else None,
    }


# ---------- tareas programadas ----------

@app.post("/internal/jobs/tick", dependencies=[Depends(require_internal)], tags=["jobs"])
def tick(reminder_hour: int = 18):
    """Recordatorio de asistencia: desde las `reminder_hour` del día anterior a la cita."""
    now = now_local().replace(tzinfo=None)
    if now.hour < reminder_hour:
        return {"sent": 0}
    tomorrow = now.date() + timedelta(days=1)
    start = datetime.combine(tomorrow, datetime.min.time())
    sent = 0
    with SessionLocal() as db:
        due = list(db.scalars(select(Appointment).where(
            Appointment.status == "confirmed", Appointment.reminder_sent.is_(False),
            Appointment.slot_at >= start, Appointment.slot_at < start + timedelta(days=1))))
        for a in due:
            msg = buttons(
                f"🔔 *Recordatorio de hora*\n\nMañana {dialog.fmt_slot(a.slot_at)} tienes "
                f"*{PRESTACION_NOMBRE.get(a.prestacion, a.prestacion)}* en "
                f"*{CENTRO_NOMBRE.get(a.center_id, a.center_id)}*.\n\n¿Asistirás?",
                [(f"agd:attend:{a.id}:yes", "✅ Asistiré"), (f"agd:attend:{a.id}:resched", "🔁 Reagendar"),
                 (f"agd:attend:{a.id}:cancel", "❌ No podré ir")],
                "Agendamiento • MedicAI",
            )
            if send(a.user_id, [msg]):
                a.reminder_sent = True
                sent += 1
                events.emit("appointment_reminder_sent", service=SERVICE, user_id=a.user_id,
                            center=a.center_id, props={"appointment_id": a.id})
        db.commit()
    return {"sent": sent}
