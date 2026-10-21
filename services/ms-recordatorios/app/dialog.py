"""Recordatorios de toma de medicamentos y registro de adherencia."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from medicai_common.contracts import DialogRequest, DialogResponse, DomainEvent, reply
from medicai_common.matching import choice, remember_menu
from medicai_common.messages import buttons, lst, text
from medicai_common.textutil import normalize, now_local, parse_times

from .models import DoseLog, Reminder, SessionLocal

FOOTER = "Recordatorios • MedicAI"
FRECUENCIAS = [
    ("rec:freq:1", "1 vez al día"),
    ("rec:freq:2", "2 veces al día", "Cada 12 horas"),
    ("rec:freq:3", "3 veces al día", "Cada 8 horas"),
    ("rec:freq:4", "4 veces al día", "Cada 6 horas"),
    ("rec:freq:custom", "Horarios personalizados", "Escribes tú las horas"),
]
def pretty(name: str) -> str:
    name = " ".join(name.split())[:80]
    return name[:1].upper() + name[1:]


PRIMERAS_HORAS = ["06:00", "07:00", "08:00", "09:00", "10:00", "12:00", "14:00", "20:00", "21:00", "22:00"]


def spread(first: str, n: int) -> list[str]:
    h, m = map(int, first.split(":"))
    step = 24 * 60 // n
    return sorted({f"{((h * 60 + m + k * step) // 60) % 24:02d}:{(m + k * step) % 60:02d}" for k in range(n)})


def ask_name(state: dict) -> DialogResponse:
    return reply(text("💊 *Recordatorio de medicamentos*\n\n"
                      "Tomar los medicamentos a tiempo es clave para que el tratamiento funcione.\n\n"
                      "✍️ ¿Cuál es el *nombre del medicamento*? (por ejemplo: _Losartán 50 mg_)"),
                 state={**state, "step": "name"})


def ask_freq(state: dict) -> DialogResponse:
    msg = lst(f"¿Cuántas veces al día tomas *{state['medication']}*?", FRECUENCIAS, FOOTER, "Ver frecuencias")
    return reply(msg, state=remember_menu({**state, "step": "freq"}, msg))


def ask_first(state: dict) -> DialogResponse:
    msg = lst("⏰ ¿A qué hora es la *primera toma* del día?\n_También puedes escribirla, ej: 07:30_",
              [(f"rec:first:{h}", h) for h in PRIMERAS_HORAS], FOOTER, "Ver horas")
    return reply(msg, state=remember_menu({**state, "step": "first"}, msg))


def ask_custom(state: dict) -> DialogResponse:
    return reply(text("✍️ Escribe las horas de cada toma, por ejemplo: *08:00 y 20:00*"),
                 state={**state, "step": "custom", "_menu": None})


def ask_confirm(state: dict) -> DialogResponse:
    msg = buttons(f"📋 Te recordaré *{state['medication']}* a las *{', '.join(state['times'])}* todos los días.\n\n"
                  "En cada aviso podrás marcar si ya la tomaste. ¿Lo dejo activo?",
                  [("rec:save:yes", "✅ Activar"), ("rec:save:no", "❌ Cancelar")], FOOTER)
    return reply(msg, state=remember_menu({**state, "step": "confirm"}, msg))


def save(req: DialogRequest) -> DialogResponse:
    st = req.state
    with SessionLocal() as db:
        existing = db.scalar(select(Reminder).where(Reminder.user_id == req.user_id, Reminder.active.is_(True),
                                                    Reminder.medication == st["medication"]))
        if existing:
            existing.times = ",".join(st["times"])
        else:
            db.add(Reminder(user_id=req.user_id, medication=st["medication"], times=",".join(st["times"]),
                            source=st.get("source", "chat")))
        db.commit()
    # No se envía el nombre del medicamento a analítica (minimización de datos, Ley 21.719).
    ev = DomainEvent(type="reminder_created", props={"doses_per_day": len(st["times"]),
                                                     "source": st.get("source", "chat"),
                                                     "updated": bool(existing)})
    return reply(text(f"✅ ¡Listo! Recordatorios de *{st['medication']}* activos a las {', '.join(st['times'])}.\n\n"
                      "Escribe *mis recordatorios* para verlos o eliminarlos. 💙"),
                 state=None, resolved=True, events=[ev])


def list_reminders(req: DialogRequest) -> DialogResponse:
    with SessionLocal() as db:
        items = list(db.scalars(select(Reminder).where(Reminder.user_id == req.user_id, Reminder.active.is_(True))
                                .order_by(Reminder.created_at)))
    if not items:
        msg = buttons("📭 No tienes recordatorios activos.", [("rec:new", "➕ Crear recordatorio")], FOOTER)
        return reply(msg, state=remember_menu({"step": "list"}, msg), resolved=True)
    body = "⏰ *Tus recordatorios activos*\n\n" + "\n".join(
        f"{i}. *{r.medication}* — {', '.join(r.time_list)}" for i, r in enumerate(items, 1))
    opts = [(f"rec:del:{r.id}", f"🗑️ {r.medication}"[:24], "Eliminar este recordatorio") for r in items[:9]]
    opts.append(("rec:new", "➕ Crear otro"))
    msg = lst(body, opts, FOOTER, "Gestionar")
    return reply(msg, state=remember_menu({"step": "list"}, msg), resolved=True)


def delete(rid: int, req: DialogRequest) -> DialogResponse:
    with SessionLocal() as db:
        r = db.get(Reminder, rid)
        if not r or r.user_id != req.user_id:
            return reply(text("No encontré ese recordatorio."), state=None)
        r.active = False
        db.commit()
        name = r.medication
    return reply(text(f"🗑️ Eliminé el recordatorio de *{name}*."), state=None, resolved=True,
                 events=[DomainEvent(type="reminder_deleted")])


def dose_answer(log_id: int, answer: str, req: DialogRequest) -> DialogResponse:
    now = now_local().replace(tzinfo=None)
    with SessionLocal() as db:
        log = db.get(DoseLog, log_id)
        if not log or log.user_id != req.user_id:
            return reply(text("No encontré esa toma."), state=None)
        if log.status in ("taken", "skipped"):
            return reply(text("Esa toma ya estaba registrada. 👍"), state=None)
        delay = round((now - log.sent_at).total_seconds() / 60, 1)
        if answer == "snooze":
            log.status = "snoozed"
            log.snooze_until = now.replace(second=0, microsecond=0) + timedelta(minutes=30)
            msg = "⏰ Te lo vuelvo a recordar en 30 minutos."
        elif answer == "taken":
            log.status = "taken"
            msg = "✅ ¡Muy bien! Toma registrada. Seguir tu tratamiento marca la diferencia. 💙"
        else:
            log.status = "skipped"
            msg = ("📝 Registré que omitiste esta toma. Si te ocurre seguido o tienes efectos adversos, "
                   "coméntalo en tu próximo control.")
        log.responded_at = now
        db.commit()
    return reply(text(msg), state=None, resolved=True,
                 events=[DomainEvent(type=f"dose_{answer if answer != 'snooze' else 'snoozed'}",
                                     props={"response_delay_min": delay})])


def handle(req: DialogRequest) -> DialogResponse:
    state = dict(req.state)
    opt = choice(req)

    if opt and opt.startswith("rec:dose:"):
        _, _, log_id, answer = opt.split(":")
        return dose_answer(int(log_id), answer, req)
    if opt and opt.startswith("rec:del:"):
        return delete(int(opt.split(":")[2]), req)
    if opt == "rec:list" or (req.start and req.intent == "ver_recordatorios"):
        return list_reminders(req)
    if req.start or opt in ("rec:new", "rec:start"):
        med = (req.entities or {}).get("medicamento")
        base = {"source": (req.entities or {}).get("source", "chat")}
        if med:
            return ask_freq({**base, "medication": pretty(str(med))})
        return ask_name(base)

    step = state.get("step")
    if step == "name":
        name = req.text.strip()
        if len(name) < 2:
            return ask_name(state)
        return ask_freq({**state, "medication": pretty(name)})
    if step == "freq":
        if opt == "rec:freq:custom":
            return ask_custom(state)
        if opt and opt.startswith("rec:freq:"):
            return ask_first({**state, "n": int(opt.split(":")[2])})
        return ask_freq(state)
    if step == "first":
        if opt and opt.startswith("rec:first:"):
            first = opt.split(":", 2)[2]
        else:
            parsed = parse_times(req.text)
            if not parsed:
                return ask_first(state)
            first = parsed[0]
        return ask_confirm({**state, "times": spread(first, state["n"])})
    if step == "custom":
        times = parse_times(req.text)
        if not times:
            return reply(text("No pude leer las horas 😕. Escríbelas así: *08:00 y 20:00*"), state=state)
        return ask_confirm({**state, "times": times})
    if step == "confirm":
        if opt == "rec:save:yes":
            return save(req)
        if opt == "rec:save:no":
            return reply(text("👍 No activé el recordatorio."), state=None)
        return ask_confirm(state)
    if "recordatorio" in normalize(req.text):
        return list_reminders(req)
    return ask_name({})
