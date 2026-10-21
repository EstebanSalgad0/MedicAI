from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from medicai_common import events
from medicai_common.centros import HOSPITAL
from medicai_common.contracts import DialogRequest, DialogResponse
from medicai_common.messages import buttons
from medicai_common.notify import send
from medicai_common.service import create_service, require_internal, setup_logging
from medicai_common.textutil import now_local

from . import dialog, gap
from .catalog import CENTRO_NOMBRE, CENTROS, ESPECIALIDADES_HRT, PRESTACION_NOMBRE, PRESTACIONES
from .models import Appointment, GapOffer, SessionLocal, Waitlist, init_db

SERVICE = "agendamiento"
log = setup_logging(SERVICE)
app = create_service(SERVICE, "Reserva, reagendamiento y cancelación de horas en CESFAM y en el Hospital Regional "
                              "de Talca, con recordatorios de 48 y 24 h, lista de espera y fill-the-gap.",
                     on_startup=init_db)


@app.post("/dialog", response_model=DialogResponse, dependencies=[Depends(require_internal)], tags=["chat"])
def post_dialog(req: DialogRequest) -> DialogResponse:
    return dialog.handle(req)


# ---------- API para el dashboard (funcionarios) ----------

class AppointmentOut(BaseModel):
    id: int
    code: str
    patient_name: str | None
    prestacion: str
    prestacion_nombre: str
    center_id: str
    center_nombre: str
    slot_at: datetime
    status: str
    attendance_reply: str | None
    channel: str
    ges: str | None = None


def _out(a: Appointment) -> AppointmentOut:
    return AppointmentOut(
        id=a.id, code=a.code, patient_name=a.patient_name, prestacion=a.prestacion,
        prestacion_nombre=PRESTACION_NOMBRE.get(a.prestacion, a.prestacion), center_id=a.center_id,
        center_nombre=CENTRO_NOMBRE.get(a.center_id, a.center_id), slot_at=a.slot_at,
        status=a.status, attendance_reply=a.attendance_reply, channel=a.channel, ges=a.ges,
    )


@app.get("/catalog", tags=["dashboard"])
def catalog():
    return {
        "centers": [{"id": k, "nombre": n, "comuna": c, "tipo": "cesfam"} for k, n, c in CENTROS]
        + [{"id": HOSPITAL[0], "nombre": HOSPITAL[1], "comuna": HOSPITAL[2], "tipo": "hospital"}],
        "prestaciones": [{"id": k, "nombre": PRESTACION_NOMBRE[k]} for k, _ in PRESTACIONES],
        "especialidades": [{"id": k, "nombre": PRESTACION_NOMBRE[k]} for k, _ in ESPECIALIDADES_HRT],
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
        previous = a.status
        a.status = body.status
        db.commit()
        out = _out(a)
    if body.status in ("attended", "no_show"):
        events.emit(f"appointment_{body.status}", service=SERVICE, user_id=a.user_id, center=a.center_id,
                    props={"appointment_id": a.id, "attendance_reply": a.attendance_reply,
                           "prestacion": a.prestacion})
    if body.status == "cancelled" and previous == "confirmed":
        gap.offer_gap(a.center_id, a.prestacion, a.slot_at)
    if body.status == "no_show" and previous != "no_show":
        # Re-agendamiento en 2 toques tras una inasistencia
        msg = buttons(f"💙 Vimos que no pudiste asistir a tu hora de *{PRESTACION_NOMBRE.get(a.prestacion, a.prestacion)}* "
                      f"en {CENTRO_NOMBRE.get(a.center_id, a.center_id)}. ¿Quieres que busquemos otra?",
                      [(f"agd:resched:{a.id}", "🔁 Reagendar"), ("sys:menu", "🏠 Menú principal")],
                      "Agendamiento • MedicAI")
        if send(a.user_id, [msg]):
            events.emit("noshow_reschedule_offered", service=SERVICE, user_id=a.user_id, center=a.center_id)
    return out


@app.get("/stats", tags=["dashboard"])
def stats(center_id: str | None = None):
    today = now_local().date()
    start = datetime.combine(today, datetime.min.time())
    with SessionLocal() as db:
        q = select(Appointment.status, func.count()).group_by(Appointment.status)
        if center_id:
            q = q.where(Appointment.center_id == center_id)
        by_status = dict(db.execute(q).all())
        by_center = [
            {"center_id": c, "center_nombre": CENTRO_NOMBRE.get(c, c), "status": s, "total": n}
            for c, s, n in db.execute(select(Appointment.center_id, Appointment.status, func.count())
                                      .group_by(Appointment.center_id, Appointment.status)).all()
        ]
        tq = select(Appointment.status, func.count()).where(
            Appointment.slot_at >= start, Appointment.slot_at < start + timedelta(days=1)).group_by(Appointment.status)
        if center_id:
            tq = tq.where(Appointment.center_id == center_id)
        hoy = dict(db.execute(tq).all())
        waiting = db.scalar(select(func.count()).select_from(Waitlist).where(Waitlist.status == "waiting"))
    closed = by_status.get("attended", 0) + by_status.get("no_show", 0)
    closed_today = hoy.get("attended", 0) + hoy.get("no_show", 0)
    return {
        "by_status": by_status,
        "by_center": by_center,
        "no_show_rate": round(by_status.get("no_show", 0) / closed, 4) if closed else None,
        "today": {"scheduled": sum(v for k, v in hoy.items() if k != "cancelled"), "attended": hoy.get("attended", 0),
                  "no_show": hoy.get("no_show", 0),
                  "no_show_rate": round(hoy.get("no_show", 0) / closed_today, 4) if closed_today else None},
        "waitlist_waiting": waiting,
    }


@app.get("/stats/daily", tags=["dashboard"])
def stats_daily(days: int = 14, center_id: str | None = None):
    """Inasistencia por día y horas recuperadas por fill-the-gap (para el panel de gestión)."""
    today = now_local().date()
    first = today - timedelta(days=days - 1)
    start = datetime.combine(first, datetime.min.time())
    end = datetime.combine(today + timedelta(days=1), datetime.min.time())
    rows: dict[str, dict] = {(first + timedelta(days=i)).isoformat(): {"attended": 0, "no_show": 0, "gap_filled": 0,
                                                                         "gap_offered": 0}
                             for i in range(days)}
    with SessionLocal() as db:
        q = select(Appointment.slot_at, Appointment.status).where(Appointment.slot_at >= start, Appointment.slot_at < end,
                                                                  Appointment.status.in_(["attended", "no_show"]))
        if center_id:
            q = q.where(Appointment.center_id == center_id)
        for slot, status in db.execute(q):
            rows[slot.date().isoformat()][status] += 1
        for when, status in db.execute(select(GapOffer.offered_at, GapOffer.status).where(GapOffer.offered_at >= start)):
            d = when.date().isoformat()
            if d in rows:
                rows[d]["gap_offered"] += 1
                rows[d]["gap_filled"] += status == "accepted"
    out = []
    for d, r in rows.items():
        closed = r["attended"] + r["no_show"]
        out.append({"date": d, **r, "no_show_rate": round(r["no_show"] / closed, 4) if closed else None})
    return out


@app.get("/waitlist", tags=["dashboard"])
def waitlist(status: str = "waiting", limit: int = 200):
    with SessionLocal() as db:
        items = list(db.scalars(select(Waitlist).where(Waitlist.status == status)
                                .order_by(Waitlist.priority.desc(), Waitlist.created_at).limit(min(limit, 1000))))
        offers = defaultdict(int)
        for wid, n in db.execute(select(GapOffer.waitlist_id, func.count()).group_by(GapOffer.waitlist_id)):
            offers[wid] = n
        return [{"id": w.id, "patient_name": w.patient_name, "channel": w.channel, "center_id": w.center_id,
                 "center_nombre": CENTRO_NOMBRE.get(w.center_id, w.center_id), "prestacion": w.prestacion,
                 "prestacion_nombre": PRESTACION_NOMBRE.get(w.prestacion, w.prestacion),
                 "earlier": bool(w.appointment_id), "priority": w.priority, "offers": offers[w.id],
                 "created_at": w.created_at} for w in items]


# ---------- tareas programadas ----------

def _reminder(a: Appointment, cuando: str):
    return buttons(
        f"🔔 *Recordatorio de hora*\n\n{cuando} {dialog.fmt_slot(a.slot_at)} tienes "
        f"*{PRESTACION_NOMBRE.get(a.prestacion, a.prestacion)}* en *{CENTRO_NOMBRE.get(a.center_id, a.center_id)}* "
        f"(código {a.code}).\n\n¿Asistirás?",
        [(f"agd:attend:{a.id}:yes", "✅ Asistiré"), (f"agd:attend:{a.id}:resched", "🔁 Reagendar"),
         (f"agd:attend:{a.id}:cancel", "❌ No podré ir")],
        "Agendamiento • MedicAI",
    )


@app.post("/internal/jobs/tick", dependencies=[Depends(require_internal)], tags=["jobs"])
def tick(reminder_hour: int = 18):
    """Recordatorios de asistencia 48 h y 24 h antes (desde las `reminder_hour`) y vencimiento
    de las ofertas de fill-the-gap."""
    expired = gap.expire_offers()
    now = now_local().replace(tzinfo=None)
    if now.hour < reminder_hour:
        return {"sent_24h": 0, "sent_48h": 0, "gap_expired": expired}
    counts = {"sent_24h": 0, "sent_48h": 0, "gap_expired": expired}
    with SessionLocal() as db:
        for days_before, flag, key, cuando in ((1, "reminder_sent", "sent_24h", "Mañana"),
                                               (2, "reminder_48_sent", "sent_48h", "Pasado mañana")):
            start = datetime.combine(now.date() + timedelta(days=days_before), datetime.min.time())
            col = getattr(Appointment, flag)
            due = list(db.scalars(select(Appointment).where(
                Appointment.status == "confirmed", (col.is_(False)) | (col.is_(None)),
                Appointment.slot_at >= start, Appointment.slot_at < start + timedelta(days=1))))
            for a in due:
                if send(a.user_id, [_reminder(a, cuando)]):
                    setattr(a, flag, True)
                    counts[key] += 1
                    events.emit("appointment_reminder_sent", service=SERVICE, user_id=a.user_id,
                                center=a.center_id, props={"appointment_id": a.id, "hours_before": days_before * 24})
        db.commit()
    return counts
