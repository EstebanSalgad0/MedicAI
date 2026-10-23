"""Flujo conversacional de agendamiento: reservar, reagendar y cancelar horas.

Dos caminos que conviven:
  - CESFAM (APS): atención → CESFAM → hora.
  - Hospital Regional de Talca: especialidad → ¿tiene interconsulta? → día → hora,
    con código de reserva HRT-XXXXXX, aviso de garantía GES y lista de espera.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select

from medicai_common.contracts import DialogRequest, DialogResponse, DomainEvent, reply
from medicai_common.matching import choice, remember_menu
from medicai_common.messages import buttons, lst, text
from medicai_common.textutil import normalize, now_local

from . import gap, perfil
from .catalog import (CENTRO_NOMBRE, CENTROS, DIAS_HABILES_A_OFRECER, ESPECIALIDADES_HRT, GES_PALABRAS, HORARIOS,
                      HORARIOS_HRT, HRT, PRESTACION_NOMBRE, PRESTACIONES, REQUIERE_DERIVACION, SOLO_HOSPITAL)
from .models import Appointment, GapOffer, SessionLocal, Waitlist

FOOTER = "Agendamiento • MedicAI"
fmt_slot = gap.fmt_slot
APS_IDS = {k for k, _ in PRESTACIONES}


# ---------- disponibilidad ----------

def _candidates(center_id: str, first: date, last: date) -> list[datetime]:
    horarios = HORARIOS_HRT if center_id == HRT else HORARIOS
    out, day = [], first
    while day <= last:
        if day.weekday() < 5:
            for h in horarios:
                hh, mm = map(int, h.split(":"))
                out.append(datetime(day.year, day.month, day.day, hh, mm))
        day += timedelta(days=1)
    return out


def free_slots(prestacion: str, center_id: str, limit: int = 9,
               first: date | None = None, last: date | None = None) -> list[datetime]:
    """Cupos libres. Sin rango: desde mañana, los próximos días hábiles (APS)."""
    now = now_local().replace(tzinfo=None)
    if first is None:
        first, n, day = now.date() + timedelta(days=1), 0, now.date()
        while n < DIAS_HABILES_A_OFRECER:
            day += timedelta(days=1)
            n += day.weekday() < 5
        last = day
    candidates = [c for c in _candidates(center_id, first, last or first) if c > now + timedelta(hours=1)]
    if not candidates:
        return []
    with SessionLocal() as db:
        taken = set(db.scalars(select(Appointment.slot_at).where(
            Appointment.prestacion == prestacion, Appointment.center_id == center_id,
            Appointment.status == "confirmed", Appointment.slot_at >= candidates[0])))
        held = set(db.scalars(select(GapOffer.slot_at).where(  # cupos reservados para una oferta de lista de espera
            GapOffer.prestacion == prestacion, GapOffer.center_id == center_id, GapOffer.status == "offered")))
    return [c for c in candidates if c not in taken and c not in held][:limit]


def day_ranges() -> dict[str, tuple[str, date, date]]:
    today = now_local().date()
    sunday = today + timedelta(days=6 - today.weekday())
    return {
        "hoy": ("Hoy", today, today),
        "manana": ("Mañana", today + timedelta(days=1), today + timedelta(days=1)),
        "semana": ("Esta semana", today + timedelta(days=2), sunday),
        "proxima": ("Próxima semana", sunday + timedelta(days=1), sunday + timedelta(days=7)),
    }


def usual_center(user_id: str) -> str | None:
    with SessionLocal() as db:
        return db.scalar(select(Appointment.center_id).where(Appointment.user_id == user_id,
                                                             Appointment.center_id != HRT)
                         .order_by(Appointment.created_at.desc()).limit(1))


def detect_ges(raw: str) -> str | None:
    t = normalize(raw)
    return next((v for k, v in GES_PALABRAS.items() if k in t), None)


# ---------- pasos comunes ----------

def ask_place(state: dict) -> DialogResponse:
    msg = buttons("📅 *Agendar una hora*\n\n¿Dónde quieres atenderte?\n"
                  "• *Hospital Regional de Talca:* especialidades (cardiología, traumatología, pediatría…).\n"
                  "• *Tu CESFAM:* medicina general, matrona, dental, controles y más.",
                  [("agd:place:hrt", "🏥 Hospital Regional"), ("agd:place:cesfam", "🏠 Mi CESFAM")], FOOTER)
    return reply(msg, state=remember_menu({**state, "step": "place"}, msg))


def ask_confirm(state: dict) -> DialogResponse:
    slot = datetime.fromisoformat(state["slot"])
    ges = (f"\n\n🛡️ Mencionaste *{state['ges']}*: si tienes ese diagnóstico confirmado, tiene garantía GES "
           "de atención en un plazo máximo y tu atención no puede condicionarse a un pago.") if state.get("ges") else ""
    msg = buttons(
        "📋 *Revisa tu reserva*\n\n"
        f"👩‍⚕️ Atención: {PRESTACION_NOMBRE[state['prestacion']]}\n"
        f"🏥 Centro: {CENTRO_NOMBRE[state['center_id']]}\n"
        f"📅 Fecha: {fmt_slot(slot)}{ges}\n\n¿Confirmas la hora?",
        [("agd:confirm:yes", "✅ Confirmar"), ("agd:confirm:no", "❌ Cancelar")],
        FOOTER,
    )
    return reply(msg, state=remember_menu({**state, "step": "confirm"}, msg))


def offer_waitlist(state: dict, motivo: str) -> DialogResponse:
    center, prest = state["center_id"], state["prestacion"]
    msg = buttons(f"😕 {motivo}\n\n🔔 Puedo dejarte en la *lista de espera*: si se libera una hora de "
                  f"{PRESTACION_NOMBRE[prest]} en {CENTRO_NOMBRE[center]}, te aviso al instante por este chat "
                  "y la tomas con un toque.",
                  [(f"agd:wl:join:{center}:{prest}", "🔔 Lista de espera"),
                   ("agd:day:menu" if center == HRT else "agd:place:cesfam", "📅 Otra opción")], FOOTER)
    return reply(msg, state=remember_menu({**state, "step": "waitlist"}, msg))


# ---------- CESFAM ----------

def ask_prestacion(state: dict, page: int = 1) -> DialogResponse:
    # controles pendientes según el perfil del paciente (crónico, niño sano, embarazo, vacunas) primero
    sug = {s["prestacion"]: s["motivo"] for s in state.get("sug") or [] if s.get("prestacion") in APS_IDS}
    orden = sorted(PRESTACIONES, key=lambda p: p[0] not in sug)
    if page == 1:
        opts = [(f"agd:esp:{k}", v, f"📌 {sug[k]}"[:72]) if k in sug else (f"agd:esp:{k}", v) for k, v in orden[:9]]
        opts.append(("agd:esp:page2", "➡️ Ver más"))
        aviso = ("📌 *Según tu ficha:* " + "; ".join(sug.values()) + ".\n\n") if sug else ""
        body = ("🏠 *Hora en tu CESFAM*\n\n" + aviso + "¿Qué tipo de atención necesitas?\n"
                "_Para especialidades, elige *Hospital Regional* en el menú de agendamiento._")
    else:
        opts = [(f"agd:esp:{k}", v) for k, v in orden[9:]] + [("agd:esp:page1", "⬅️ Volver")]
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
        return offer_waitlist(state, "No quedan horas disponibles en los próximos días para esa atención.")
    opts = [("agd:slot:asap", "⚡ Lo antes posible", fmt_slot(slots[0]))]
    opts += [(f"agd:slot:{s:%Y-%m-%dT%H:%M}", fmt_slot(s)) for s in slots[:9]]
    msg = lst(f"🏥 *{CENTRO_NOMBRE[state['center_id']]}*\nElige día y hora:", opts, FOOTER, "Ver horas")
    return reply(msg, state=remember_menu({**state, "step": "slot"}, msg))


# ---------- Hospital Regional ----------

def ask_especialidad(state: dict) -> DialogResponse:
    opts = [(f"agd:hesp:{k}", v, "Requiere interconsulta" if k in REQUIERE_DERIVACION else None)
            for k, v in ESPECIALIDADES_HRT]
    msg = lst("🏥 *Hora en el Hospital Regional de Talca*\n\n¿Qué especialidad necesitas?",
              [(o[0], o[1], o[2]) if o[2] else (o[0], o[1]) for o in opts], FOOTER, "Ver especialidades")
    return reply(msg, state=remember_menu({**state, "center_id": HRT, "step": "hesp"}, msg))


def ask_derivacion(state: dict) -> DialogResponse:
    msg = buttons(f"Para *{PRESTACION_NOMBRE[state['prestacion']]}* en el hospital se necesita una "
                  "*interconsulta* (orden de derivación) de tu CESFAM.\n\n¿Ya la tienes?",
                  [("agd:deriv:yes", "✅ Sí, la tengo"), ("agd:deriv:no", "❌ No la tengo")], FOOTER)
    return reply(msg, state=remember_menu({**state, "step": "deriv"}, msg))


def no_derivacion(state: dict) -> DialogResponse:
    msg = buttons(
        "📄 *Cómo obtener la interconsulta*\n\n"
        "1. Pide una hora de *medicina general en tu CESFAM*.\n"
        "2. El médico evalúa tu caso y, si corresponde, emite la interconsulta al hospital.\n"
        "3. El hospital te contacta, o puedes agendar aquí cuando la tengas.\n\n"
        "Te ayudo con el primer paso:",
        [("agd:place:cesfam", "🏠 Hora en mi CESFAM"), ("der:type:interconsulta", "🧭 Interconsultas")],
        FOOTER)
    return reply(msg, state=None, resolved=True,
                 events=[DomainEvent(type="referral_required", props={"prestacion": state["prestacion"]})])


def ask_day(state: dict) -> DialogResponse:
    opts = []
    for key, (label, first, last) in day_ranges().items():
        n = len(free_slots(state["prestacion"], HRT, limit=500, first=first, last=last))
        opts.append((f"agd:day:{key}", label, f"{n} horas disponibles" if n else "Sin horas disponibles"))
    msg = lst(f"👩‍⚕️ *{PRESTACION_NOMBRE[state['prestacion']]}* · Hospital Regional de Talca\n¿Para cuándo?",
              opts, FOOTER, "Ver días")
    return reply(msg, state=remember_menu({**state, "center_id": HRT, "step": "day"}, msg))


def ask_slot_day(state: dict, key: str) -> DialogResponse:
    label, first, last = day_ranges()[key]
    slots = free_slots(state["prestacion"], HRT, limit=5, first=first, last=last)
    if not slots:
        return offer_waitlist({**state, "center_id": HRT}, f"No hay horas disponibles para *{label.lower()}*.")
    opts = [(f"agd:slot:{s:%Y-%m-%dT%H:%M}", fmt_slot(s)) for s in slots] + [("agd:day:menu", "⬅️ Otro día")]
    msg = lst(f"📅 *{label}* · {PRESTACION_NOMBRE[state['prestacion']]}\nElige tu hora:", opts, FOOTER, "Ver horas")
    return reply(msg, state=remember_menu({**state, "center_id": HRT, "step": "slot"}, msg))


def hospital_start(state: dict) -> DialogResponse:
    if state["prestacion"] in REQUIERE_DERIVACION:
        return ask_derivacion(state)
    return ask_day(state)


# ---------- reserva y gestión ----------

def book(req: DialogRequest) -> DialogResponse:
    st = req.state
    slot = datetime.fromisoformat(st["slot"])
    if slot not in free_slots(st["prestacion"], st["center_id"], limit=1000,
                              first=slot.date(), last=slot.date()):
        return (ask_day if st["center_id"] == HRT else ask_slot)({**st, "slot": None})  # alguien la tomó
    with SessionLocal() as db:
        appt = Appointment(user_id=req.user_id, patient_name=req.name, channel=req.channel, ges=st.get("ges"),
                           prestacion=st["prestacion"], center_id=st["center_id"], slot_at=slot)
        if st.get("rescheduled_from"):
            old = db.get(Appointment, st["rescheduled_from"])
            if old and old.user_id == req.user_id:
                old.status = "cancelled"
                freed = (old.center_id, old.prestacion, old.slot_at)
            else:
                freed = None
        else:
            freed = None
        db.add(appt)
        db.commit()
        appt_id, code = appt.id, appt.code
    if freed:
        gap.offer_gap(*freed)
    hosp = st["center_id"] == HRT
    ev = DomainEvent(type="appointment_booked", center=st["center_id"],
                     props={"appointment_id": appt_id, "prestacion": st["prestacion"], "hospital": hosp,
                            "ges": bool(st.get("ges")), "lead_days": (slot.date() - now_local().date()).days,
                            "rescheduled": bool(st.get("rescheduled_from"))})
    ges = (f"🛡️ Si tu diagnóstico de *{st['ges']}* está confirmado, tienes garantía GES: atención en plazo "
           "máximo y sin condicionarla a pago.\n\n") if st.get("ges") else ""
    llevar = "tu cédula de identidad y la interconsulta" if hosp and st["prestacion"] in REQUIERE_DERIVACION \
        else "tu cédula de identidad"
    return reply(
        text("🎉 *¡Hora agendada!*\n\n"
             f"🔖 Código de reserva: *{code}*\n"
             f"📅 {fmt_slot(slot)}\n🏥 {CENTRO_NOMBRE[st['center_id']]}\n"
             f"👩‍⚕️ {PRESTACION_NOMBRE[st['prestacion']]}\n\n"
             "🔔 Te enviaré recordatorios *48 h y 24 h antes* por WhatsApp para confirmar tu asistencia.\n"
             f"💡 Llega 15 minutos antes con {llevar}.\n\n{ges}"
             "Para cambiarla o cancelarla escribe *reprogramar mi hora*."),
        state=None, resolved=True, events=[ev],
    )


def my_appointments(req: DialogRequest) -> DialogResponse:
    now = now_local().replace(tzinfo=None)
    with SessionLocal() as db:
        appts = list(db.scalars(
            select(Appointment).where(Appointment.user_id == req.user_id, Appointment.status == "confirmed",
                                      Appointment.slot_at >= now)
            .order_by(Appointment.slot_at).limit(9)))
    if not appts:
        msg = buttons("📭 No tienes horas agendadas.", [("agd:new", "📅 Agendar hora")], FOOTER)
        return reply(msg, state=remember_menu({"step": "mine"}, msg), resolved=True)
    opts = [(f"agd:manage:{a.id}", fmt_slot(a.slot_at),
             f"{a.code} · {PRESTACION_NOMBRE.get(a.prestacion, a.prestacion)} · {CENTRO_NOMBRE.get(a.center_id, a.center_id)}")
            for a in appts]
    msg = lst("📋 *Tus próximas horas*\nSelecciona una para cambiarla o cancelarla:", opts, FOOTER, "Ver horas")
    return reply(msg, state=remember_menu({"step": "mine"}, msg))


def manage(appt_id: int, req: DialogRequest) -> DialogResponse:
    with SessionLocal() as db:
        a = db.get(Appointment, appt_id)
    if not a or a.user_id != req.user_id:
        return reply(text("No encontré esa hora."), state=None)
    msg = lst(
        f"🔖 {a.code}\n📅 {fmt_slot(a.slot_at)} · {PRESTACION_NOMBRE.get(a.prestacion, a.prestacion)}\n"
        f"🏥 {CENTRO_NOMBRE.get(a.center_id, a.center_id)}\n\n¿Qué quieres hacer?",
        [(f"agd:resched:{a.id}", "🔁 Cambiar día u hora"), (f"agd:cancel:{a.id}", "🗑️ Cancelar hora"),
         (f"agd:wl:earlier:{a.id}", "⚡ Avisarme si hay antes", "Mantienes tu hora y te aviso si se libera una antes"),
         ("agd:keep", "↩️ Mantener")],
        FOOTER, "Ver opciones")
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
        center, prest, slot = a.center_id, a.prestacion, a.slot_at
    gap.offer_gap(center, prest, slot)  # el cupo pasa al siguiente de la lista de espera
    ev = DomainEvent(type="appointment_cancelled", center=center,
                     props={"appointment_id": appt_id, "origin": origin,
                            "hours_before": round((slot - now_local().replace(tzinfo=None)).total_seconds() / 3600, 1)})
    msg = buttons("🗑️ Hora cancelada. El cupo quedó liberado para otra persona. ¡Gracias por avisar! 💙\n\n"
                  "Si necesitas otra hora, puedo avisarte apenas se libere una.",
                  [(f"agd:wl:join:{center}:{prest}", "🔔 Lista de espera")], FOOTER)
    return reply(msg, state=None, resolved=True, events=[ev])


def reschedule(appt_id: int, req: DialogRequest) -> DialogResponse:
    with SessionLocal() as db:
        a = db.get(Appointment, appt_id)
    if not a or a.user_id != req.user_id or a.status not in ("confirmed", "no_show"):
        return reply(text("Esa hora ya no está vigente."), state=None)
    base = {"prestacion": a.prestacion, "center_id": a.center_id,
            "rescheduled_from": a.id if a.status == "confirmed" else None}
    return ask_day(base) if a.center_id == HRT else ask_slot(base)


def waitlist_join(req: DialogRequest, center: str, prest: str, appointment_id: int | None = None,
                  priority: int = 0) -> DialogResponse:
    with SessionLocal() as db:
        if appointment_id:
            a = db.get(Appointment, appointment_id)
            if not a or a.user_id != req.user_id or a.status != "confirmed":
                return reply(text("Esa hora ya no está vigente."), state=None)
            center, prest, priority = a.center_id, a.prestacion, int(bool(a.ges))
        exists = db.scalar(select(Waitlist).where(Waitlist.user_id == req.user_id, Waitlist.center_id == center,
                                                  Waitlist.prestacion == prest, Waitlist.status == "waiting"))
        if exists:
            exists.appointment_id = appointment_id or exists.appointment_id
        else:
            db.add(Waitlist(user_id=req.user_id, patient_name=req.name, channel=req.channel, center_id=center,
                            prestacion=prest, appointment_id=appointment_id, priority=priority))
        db.commit()
    detalle = "una hora antes que la tuya" if appointment_id else "una hora"
    return reply(text(f"🔔 Listo, quedaste en la *lista de espera* de {PRESTACION_NOMBRE.get(prest, prest)} en "
                      f"{CENTRO_NOMBRE.get(center, center)}.\n\nSi se libera {detalle}, te aviso al instante por "
                      "este chat y la tomas con un toque."),
                 state=None, resolved=True,
                 events=[DomainEvent(type="waitlist_joined", center=center,
                                     props={"prestacion": prest, "earlier": bool(appointment_id),
                                            "priority": priority})])


def gap_answer(offer_id: int, answer: str, req: DialogRequest) -> DialogResponse:
    now = now_local().replace(tzinfo=None)
    with SessionLocal() as db:
        offer = db.get(GapOffer, offer_id)
        wl = db.get(Waitlist, offer.waitlist_id) if offer else None
        if not offer or not wl or wl.user_id != req.user_id:
            return reply(text("No encontré esa oferta."), state=None)
        if offer.status != "offered":
            return reply(text("⌛ Esa hora ya no está disponible: la oferta venció o la tomó otra persona. "
                              "Sigues en la lista de espera y te aviso si se libera otra."), state=None)
        slot, center, prest = offer.slot_at, offer.center_id, offer.prestacion
        if answer != "yes":
            offer.status, offer.answered_at = "declined", now
            db.commit()
            gap.offer_gap(center, prest, slot)
            return reply(text("👍 Sin problema. Sigues en la lista de espera por si se libera otra hora."),
                         state=None, resolved=True)
        taken = db.scalar(select(Appointment.id).where(Appointment.center_id == center, Appointment.prestacion == prest,
                                                       Appointment.slot_at == slot, Appointment.status == "confirmed"))
        if taken:
            offer.status = "taken"
            db.commit()
            return reply(text("😕 Justo la tomó otra persona. Sigues en la lista de espera."), state=None)
        appt = Appointment(user_id=wl.user_id, patient_name=wl.patient_name or req.name, channel=wl.channel,
                           prestacion=prest, center_id=center, slot_at=slot)
        db.add(appt)
        previous = db.get(Appointment, wl.appointment_id) if wl.appointment_id else None
        if previous and previous.status == "confirmed":
            previous.status = "cancelled"
            freed = (previous.center_id, previous.prestacion, previous.slot_at)
        else:
            freed = None
        offer.status, offer.answered_at, wl.status = "accepted", now, "booked"
        db.commit()
        code, appt_id = appt.code, appt.id
    if freed:
        gap.offer_gap(*freed)  # la hora que dejó pasa al siguiente: efecto cadena
    events = [DomainEvent(type="gap_filled", center=center,
                          props={"appointment_id": appt_id, "prestacion": prest, "earlier": bool(freed),
                                 "hours_before_slot": round((slot - now).total_seconds() / 3600, 1)}),
              DomainEvent(type="appointment_booked", center=center,
                          props={"appointment_id": appt_id, "prestacion": prest, "hospital": center == HRT,
                                 "from_waitlist": True, "lead_days": (slot.date() - now.date()).days,
                                 "rescheduled": bool(freed)})]
    cambio = "\n♻️ Liberé tu hora anterior para otra persona." if freed else ""
    return reply(text(f"🎉 *¡Hora tomada!*\n\n🔖 Código: *{code}*\n📅 {fmt_slot(slot)}\n"
                      f"🏥 {CENTRO_NOMBRE.get(center, center)}\n👩‍⚕️ {PRESTACION_NOMBRE.get(prest, prest)}{cambio}\n\n"
                      "🔔 Te enviaré recordatorios 48 h y 24 h antes."),
                 state=None, resolved=True, events=events)


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

def start(req: DialogRequest) -> DialogResponse:
    if req.intent in ("ver_citas", "cancelar_cita"):
        return my_appointments(req)
    ents = req.entities or {}
    prest = ents.get("prestacion")
    ges = detect_ges(req.text)
    base = {"ges": ges} if ges else {}
    if prest in SOLO_HOSPITAL:  # "quiero hora con el cardiólogo"
        return hospital_start({**base, "prestacion": prest, "center_id": HRT})
    if prest in APS_IDS:  # "quiero hora con la matrona" salta directo al CESFAM
        return ask_center({**base, "prestacion": prest}, req.user_id)
    if "hospital" in normalize(req.text):
        return ask_especialidad(base)
    return ask_place(base)


def handle(req: DialogRequest) -> DialogResponse:
    state = dict(req.state)
    opt = choice(req)

    if req.start or opt in ("agd:new", "agd:start"):
        return start(req) if req.start else ask_place({})
    if opt == "agd:mine":
        return my_appointments(req)

    if opt is None:
        # Texto libre que no calza con el menú: repetimos el paso actual.
        step = state.get("step")
        repeat = {"place": lambda: ask_place(state), "prestacion": lambda: ask_prestacion(state),
                  "center": lambda: ask_center(state, req.user_id), "slot": lambda: ask_slot(state)
                  if state.get("center_id") != HRT else ask_day(state),
                  "hesp": lambda: ask_especialidad(state), "deriv": lambda: ask_derivacion(state),
                  "day": lambda: ask_day(state), "confirm": lambda: ask_confirm(state),
                  "waitlist": lambda: offer_waitlist(state, "Elige una opción:")}
        if step in repeat:
            return repeat[step]()
        if any(w in normalize(req.text) for w in ("mis citas", "mis horas", "reprogramar")):
            return my_appointments(req)
        return ask_place({})

    parts = opt.split(":")
    action = parts[1] if len(parts) > 1 else ""
    arg = parts[2] if len(parts) > 2 else ""

    # Botón antiguo de un trámite que ya terminó o expiró: faltan los datos de los pasos previos.
    needs = {"center": ("prestacion",), "slot": ("prestacion", "center_id"), "day": ("prestacion",),
             "deriv": ("prestacion",), "confirm": ("prestacion", "center_id", "slot") if arg == "yes" else ()}
    if any(not state.get(k) for k in needs.get(action, ())):
        return reply(text("⌛ Ese botón ya no está vigente: la reserva ya se procesó o pasó mucho tiempo.\n"
                          "Escribe *mis horas* para ver tus reservas o *agendar hora* para pedir una nueva."),
                     state=None)

    if action == "place":
        if arg == HRT:
            return ask_especialidad(state)
        return ask_prestacion({**state, "sug": perfil.sugeridos(req.user_id)})
    if action == "esp":
        if arg in ("page1", "page2"):
            return ask_prestacion(state, page=int(arg[-1]))
        return ask_center({**state, "prestacion": arg}, req.user_id)
    if action == "hesp":
        return hospital_start({**state, "prestacion": arg, "center_id": HRT})
    if action == "deriv":
        return ask_day(state) if arg == "yes" else no_derivacion(state)
    if action == "center":
        return ask_slot({**state, "center_id": arg})
    if action == "day":
        return ask_day(state) if arg == "menu" else ask_slot_day(state, arg)
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
    if action == "wl":
        if arg == "earlier":
            return waitlist_join(req, "", "", appointment_id=int(parts[3]))
        center = parts[3] if len(parts) > 3 else state.get("center_id")
        prest = parts[4] if len(parts) > 4 else state.get("prestacion")
        return waitlist_join(req, center, prest, priority=int(bool(state.get("ges"))))
    if action == "gap":
        return gap_answer(int(arg), parts[3] if len(parts) > 3 else "no", req)
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
    return ask_place({})

