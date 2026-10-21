"""Flujo conversacional de agendamiento: reservar, reagendar y cancelar horas."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from medicai_common.contracts import DialogRequest, DialogResponse, DomainEvent, reply
from medicai_common.matching import choice, remember_menu
from medicai_common.messages import buttons, lst, text
from medicai_common.textutil import now_local, normalize

from .catalog import (CENTRO_NOMBRE, CENTROS, DIAS_HABILES_A_OFRECER, HORARIOS,
                      PRESTACION_NOMBRE, PRESTACIONES)
from .models import Appointment, SessionLocal

DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
FOOTER = "Agendamiento • MedicAI"


def fmt_slot(dt: datetime) -> str:
    return f"{DIAS[dt.weekday()]} {dt:%d-%m} · {dt:%H:%M}"


def free_slots(prestacion: str, center_id: str, limit: int = 9) -> list[datetime]:
    now = now_local().replace(tzinfo=None)
    day = now.date() + timedelta(days=1)
    candidates: list[datetime] = []
    offered_days = 0
    while offered_days < DIAS_HABILES_A_OFRECER:
        if day.weekday() < 5:
            offered_days += 1
            for h in HORARIOS:
                hh, mm = map(int, h.split(":"))
                candidates.append(datetime(day.year, day.month, day.day, hh, mm))
        day += timedelta(days=1)
    with SessionLocal() as db:
        taken = set(db.scalars(
            select(Appointment.slot_at).where(
                Appointment.prestacion == prestacion,
                Appointment.center_id == center_id,
                Appointment.status == "confirmed",
                Appointment.slot_at >= candidates[0],
            )
        ))
    return [c for c in candidates if c not in taken][:limit]


def usual_center(user_id: str) -> str | None:
    with SessionLocal() as db:
        return db.scalar(
            select(Appointment.center_id)
            .where(Appointment.user_id == user_id)
            .order_by(Appointment.created_at.desc())
            .limit(1)
        )


# ---------- pasos ----------

def ask_prestacion(state: dict, page: int = 1) -> DialogResponse:
    if page == 1:
        opts = [(f"agd:esp:{k}", v) for k, v in PRESTACIONES[:9]] + [("agd:esp:page2", "➡️ Ver más")]
        body = ("🗓️ *Agendamiento de horas en tu CESFAM*\n\n"
                "¿Qué tipo de atención necesitas?\n"
                "_Para especialistas (cardiología, traumatología, etc.) se requiere interconsulta: "
                "escribe *guía de ruta*._")
    else:
        opts = [(f"agd:esp:{k}", v) for k, v in PRESTACIONES[9:]] + [("agd:esp:page1", "⬅️ Volver")]
        body = "Otras atenciones disponibles:"
    msg = lst(body, opts, FOOTER, "Ver atenciones")
    return reply(msg, state=remember_menu({**state, "step": "prestacion"}, msg))


def ask_center(state: dict, user_id: str) -> DialogResponse:
    usual = usual_center(user_id)
    ordered = sorted(CENTROS, key=lambda c: c[0] != usual)
    opts = [(f"agd:center:{k}", n, f"{comuna}{' · tu CESFAM habitual' if k == usual else ''}")
            for k, n, comuna in ordered]
    msg = lst(f"Atención: *{PRESTACION_NOMBRE[state['prestacion']]}*.\n¿En qué CESFAM te atiendes?",
              opts, FOOTER, "Ver CESFAM")
    return reply(msg, state=remember_menu({**state, "step": "center"}, msg))


def ask_slot(state: dict) -> DialogResponse:
    slots = free_slots(state["prestacion"], state["center_id"])
    if not slots:
        return reply(text("😕 No quedan horas disponibles en los próximos días para esa atención en ese CESFAM. "
                          "Prueba con otro centro o vuelve a intentarlo mañana."), state=None)
    opts = [("agd:slot:asap", "⚡ Lo antes posible", fmt_slot(slots[0]))]
    opts += [(f"agd:slot:{s:%Y-%m-%dT%H:%M}", fmt_slot(s)) for s in slots[:9]]
    msg = lst(f"🏥 *{CENTRO_NOMBRE[state['center_id']]}*\nElige día y hora:", opts, FOOTER, "Ver horas")
    return reply(msg, state=remember_menu({**state, "step": "slot"}, msg))


def ask_confirm(state: dict) -> DialogResponse:
    slot = datetime.fromisoformat(state["slot"])
    msg = buttons(
        "📋 *Revisa tu reserva*\n\n"
        f"👩‍⚕️ Atención: {PRESTACION_NOMBRE[state['prestacion']]}\n"
        f"🏥 Centro: {CENTRO_NOMBRE[state['center_id']]}\n"
        f"📅 Fecha: {fmt_slot(slot)}\n\n¿Confirmas la hora?",
        [("agd:confirm:yes", "✅ Confirmar"), ("agd:confirm:no", "❌ Cancelar")],
        FOOTER,
    )
    return reply(msg, state=remember_menu({**state, "step": "confirm"}, msg))


def book(req: DialogRequest) -> DialogResponse:
    st = req.state
    slot = datetime.fromisoformat(st["slot"])
    if slot not in free_slots(st["prestacion"], st["center_id"], limit=200):
        return ask_slot({**st, "slot": None})  # alguien la tomó mientras tanto
    with SessionLocal() as db:
        appt = Appointment(user_id=req.user_id, patient_name=req.name, channel=req.channel,
                           prestacion=st["prestacion"], center_id=st["center_id"], slot_at=slot)
        if st.get("rescheduled_from"):
            old = db.get(Appointment, st["rescheduled_from"])
            if old and old.user_id == req.user_id:
                old.status = "cancelled"
        db.add(appt)
        db.commit()
        appt_id = appt.id
    ev = DomainEvent(type="appointment_booked", center=st["center_id"],
                     props={"appointment_id": appt_id, "prestacion": st["prestacion"],
                            "lead_days": (slot.date() - now_local().date()).days,
                            "rescheduled": bool(st.get("rescheduled_from"))})
    return reply(
        text("🎉 *¡Hora agendada!*\n\n"
             f"📅 {fmt_slot(slot)}\n🏥 {CENTRO_NOMBRE[st['center_id']]}\n"
             f"👩‍⚕️ {PRESTACION_NOMBRE[st['prestacion']]}\n\n"
             "🔔 Te enviaré un recordatorio el día anterior para confirmar tu asistencia.\n"
             "💡 Llega 15 minutos antes con tu cédula de identidad.\n\n"
             "Para ver o cancelar tus horas escribe *mis citas*."),
        state=None, resolved=True, events=[ev],
    )


def my_appointments(req: DialogRequest) -> DialogResponse:
    now = now_local().replace(tzinfo=None)
    with SessionLocal() as db:
        appts = list(db.scalars(
            select(Appointment).where(Appointment.user_id == req.user_id,
                                      Appointment.status == "confirmed",
                                      Appointment.slot_at >= now)
            .order_by(Appointment.slot_at).limit(9)
        ))
    if not appts:
        msg = buttons("📭 No tienes horas agendadas.", [("agd:new", "🗓️ Agendar hora")], FOOTER)
        return reply(msg, state=remember_menu({"step": "mine"}, msg), resolved=True)
    opts = [(f"agd:manage:{a.id}", fmt_slot(a.slot_at),
             f"{PRESTACION_NOMBRE.get(a.prestacion, a.prestacion)} · {CENTRO_NOMBRE.get(a.center_id, a.center_id)}")
            for a in appts]
    msg = lst("📋 *Tus próximas horas*\nSelecciona una para reagendar o cancelar:", opts, FOOTER, "Ver horas")
    return reply(msg, state=remember_menu({"step": "mine"}, msg))


def manage(appt_id: int, req: DialogRequest) -> DialogResponse:
    with SessionLocal() as db:
        a = db.get(Appointment, appt_id)
    if not a or a.user_id != req.user_id:
        return reply(text("No encontré esa hora."), state=None)
    msg = buttons(
        f"📅 {fmt_slot(a.slot_at)} · {PRESTACION_NOMBRE.get(a.prestacion, a.prestacion)}\n"
        f"🏥 {CENTRO_NOMBRE.get(a.center_id, a.center_id)}\n\n¿Qué quieres hacer?",
        [(f"agd:resched:{a.id}", "🔁 Reagendar"), (f"agd:cancel:{a.id}", "🗑️ Cancelar hora"),
         ("agd:keep", "↩️ Mantener")],
        FOOTER,
    )
    return reply(msg, state=remember_menu({"step": "manage"}, msg))


def cancel(appt_id: int, req: DialogRequest, origin: str = "chat") -> DialogResponse:
    with SessionLocal() as db:
        a = db.get(Appointment, appt_id)
        if not a or a.user_id != req.user_id or a.status != "confirmed":
            return reply(text("Esa hora ya no está vigente."), state=None)
        a.status = "cancelled"
        if origin == "reminder":
            a.attendance_reply = "cancel"
        db.commit()
        center, slot = a.center_id, a.slot_at
    ev = DomainEvent(type="appointment_cancelled", center=center,
                     props={"appointment_id": appt_id, "origin": origin,
                            "hours_before": round((slot - now_local().replace(tzinfo=None)).total_seconds() / 3600, 1)})
    return reply(text("🗑️ Hora cancelada. El cupo quedó liberado para otra persona. ¡Gracias por avisar! 💙"),
                 state=None, resolved=True, events=[ev])


def reschedule(appt_id: int, req: DialogRequest) -> DialogResponse:
    with SessionLocal() as db:
        a = db.get(Appointment, appt_id)
    if not a or a.user_id != req.user_id or a.status != "confirmed":
        return reply(text("Esa hora ya no está vigente."), state=None)
    return ask_slot({"prestacion": a.prestacion, "center_id": a.center_id, "rescheduled_from": a.id})


def attendance(appt_id: int, answer: str, req: DialogRequest) -> DialogResponse:
    if answer == "cancel":
        return cancel(appt_id, req, origin="reminder")
    if answer == "resched":
        with SessionLocal() as db:
            a = db.get(Appointment, appt_id)
            if a and a.user_id == req.user_id:
                a.attendance_reply = "reschedule"
                db.commit()
        return reschedule(appt_id, req)
    with SessionLocal() as db:
        a = db.get(Appointment, appt_id)
        if not a or a.user_id != req.user_id:
            return reply(text("No encontré esa hora."), state=None)
        a.attendance_reply = "yes"
        db.commit()
        center = a.center_id
    return reply(text("✅ ¡Gracias por confirmar! Te esperamos. Recuerda llegar 15 minutos antes."),
                 state=None, resolved=True,
                 events=[DomainEvent(type="attendance_confirmed", center=center, props={"appointment_id": appt_id})])


# ---------- punto de entrada ----------

def handle(req: DialogRequest) -> DialogResponse:
    state = dict(req.state)
    opt = choice(req)

    if req.start or opt in ("agd:new", "agd:start"):
        if req.intent in ("ver_citas", "cancelar_cita"):
            return my_appointments(req)
        prest = (req.entities or {}).get("prestacion")
        if prest in PRESTACION_NOMBRE:  # "quiero hora con la matrona" salta directo al CESFAM
            return ask_center({"prestacion": prest}, req.user_id)
        return ask_prestacion({})

    if opt is None:
        # Texto libre que no calza con el menú: repetimos el paso actual.
        step = state.get("step")
        if step == "prestacion":
            return ask_prestacion(state)
        if step == "center":
            return ask_center(state, req.user_id)
        if step == "slot":
            return ask_slot(state)
        if step == "confirm":
            return ask_confirm(state)
        if any(w in normalize(req.text) for w in ("mis citas", "mis horas")):
            return my_appointments(req)
        return ask_prestacion({})

    parts = opt.split(":")
    action = parts[1] if len(parts) > 1 else ""
    arg = parts[2] if len(parts) > 2 else ""

    if action == "esp":
        if arg in ("page1", "page2"):
            return ask_prestacion(state, page=int(arg[-1]))
        state["prestacion"] = arg
        return ask_center(state, req.user_id)
    if action == "center":
        state["center_id"] = arg
        return ask_slot(state)
    if action == "slot":
        if arg == "asap":
            slots = free_slots(state["prestacion"], state["center_id"], limit=1)
            if not slots:
                return ask_slot(state)
            state["slot"] = slots[0].isoformat()
        else:
            state["slot"] = ":".join(parts[2:])
        return ask_confirm(state)
    if action == "confirm":
        if arg == "yes":
            return book(req)
        return reply(text("👍 Reserva descartada. Cuando quieras, escribe *agendar hora*."), state=None,
                     events=[DomainEvent(type="appointment_aborted", props={"step": "confirm"})])
    if action == "mine":
        return my_appointments(req)
    if action == "manage":
        return manage(int(arg), req)
    if action == "cancel":
        return cancel(int(arg), req)
    if action == "resched":
        return reschedule(int(arg), req)
    if action == "keep":
        return reply(text("👍 Tu hora se mantiene."), state=None, resolved=True)
    if action == "attend":
        return attendance(int(arg), parts[3] if len(parts) > 3 else "yes", req)
    return ask_prestacion({})
