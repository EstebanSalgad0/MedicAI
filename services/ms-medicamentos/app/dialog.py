"""Disponibilidad de fármacos y programación de retiros en la farmacia del CESFAM."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from medicai_common.centros import CENTRO_NOMBRE, CENTROS
from medicai_common.contracts import DialogRequest, DialogResponse, DomainEvent, Handoff, reply
from medicai_common.matching import choice, remember_menu
from medicai_common.messages import Message, buttons, lst, text
from medicai_common.textutil import parse_date, parse_times, today_local

from . import stock_provider
from .models import Pickup, SessionLocal, StockAlert

FOOTER = "Farmacia • MedicAI"
STATUS_TXT = {
    "available": "✅ *{m}* está *disponible* en {c}.",
    "low": "⚠️ Queda *poco stock* de *{m}* en {c}. Te recomiendo ir pronto.",
    "none": "❌ Por ahora *no hay stock* de *{m}* en {c}.",
    "unknown": "ℹ️ No tengo información en línea del stock de *{m}* en {c}. Te recomiendo confirmarlo en la farmacia.",
}


def fmt_date(d) -> str:
    return d.strftime("%d-%m-%Y")


def ask_rx() -> DialogResponse:
    msg = lst("💊 *Farmacia de tu CESFAM*\n\nTe ayudo a revisar disponibilidad y a no olvidar tus retiros.\n"
              "¿Tienes una *receta activa* por retirar?",
              [("med:rx:yes", "✅ Sí, tengo receta"), ("med:rx:unsure", "🤔 No estoy seguro/a"),
               ("med:rx:no", "❌ No tengo receta"), ("med:list", "📋 Ver mis retiros")], FOOTER, "Responder")
    return reply(msg, state=remember_menu({"step": "rx"}, msg))


def ask_center(state: dict) -> DialogResponse:
    msg = lst(f"¿En qué CESFAM retiras *{state['medication']}*?",
              [(f"med:center:{k}", n, comuna) for k, n, comuna in CENTROS], FOOTER, "Ver CESFAM")
    return reply(msg, state=remember_menu({**state, "step": "center"}, msg))


def availability(state: dict) -> DialogResponse:
    status, canonical = stock_provider.check(state["center_id"], state["medication"])
    state = {**state, "medication": canonical, "stock_status": status}
    info = text(STATUS_TXT[status].format(m=canonical, c=CENTRO_NOMBRE[state["center_id"]]))
    ev = DomainEvent(type="stock_checked", center=state["center_id"], props={"status": status})
    if status == "none":
        msg = buttons("¿Quieres que te avise cuando vuelva a haber stock?",
                      [("med:alert:yes", "🔔 Sí, avísame"), ("med:alert:no", "No, gracias")], FOOTER)
        return reply(info, msg, state=remember_menu({**state, "step": "alert"}, msg), events=[ev])
    msg = lst("📅 Organicemos tus retiros. ¿Cada cuánto te corresponde retirar?",
              [("med:freq:30", "Cada 30 días"), ("med:freq:15", "Cada 15 días"), ("med:freq:7", "Cada 7 días"),
               ("med:freq:0", "Solo una vez")], FOOTER, "Elegir")
    return reply(info, msg, state=remember_menu({**state, "step": "freq"}, msg), events=[ev])


def ask_next(state: dict) -> DialogResponse:
    today = today_local()
    msg = lst("¿Cuándo es tu *próximo retiro*?\n_También puedes escribir la fecha, ej: 05-11-2026_",
              [(f"med:next:{(today + timedelta(days=d)).isoformat()}", lbl)
               for d, lbl in [(0, "Hoy"), (1, "Mañana"), (3, "En 3 días"), (7, "En 1 semana"), (14, "En 2 semanas")]],
              FOOTER, "Elegir fecha")
    return reply(msg, state=remember_menu({**state, "step": "next"}, msg))


def ask_hour(state: dict) -> DialogResponse:
    msg = buttons("⏰ ¿A qué hora te aviso ese día?",
                  [("med:hour:08:00", "08:00"), ("med:hour:12:00", "12:00"), ("med:hour:17:00", "17:00")], FOOTER)
    return reply(msg, state=remember_menu({**state, "step": "hour"}, msg))


def save(req: DialogRequest, state: dict) -> DialogResponse:
    with SessionLocal() as db:
        p = Pickup(user_id=req.user_id, medication=state["medication"], center_id=state["center_id"],
                   due_date=parse_date(state["next"]), hour=state["hour"], freq_days=state["freq"] or None)
        db.add(p)
        db.commit()
    ciclo = f"cada *{state['freq']} días*" if state["freq"] else "una vez"
    msg = buttons(f"✅ Listo. Retiro de *{state['medication']}* {ciclo}, próximo el *{fmt_date(p.due_date)}*.\n"
                  "🔔 Te avisaré 3 días antes y el mismo día, y te preguntaré si pudiste retirar.\n\n"
                  "¿Quieres además recordatorios para *tomar* este medicamento?",
                  [("med:link:yes", "⏰ Sí, recordar tomas"), ("med:link:no", "No, gracias")], FOOTER)
    ev = DomainEvent(type="pickup_scheduled", center=state["center_id"],
                     props={"freq_days": state["freq"], "stock_status": state.get("stock_status")})
    return reply(msg, state=remember_menu({"step": "link", "medication": state["medication"]}, msg),
                 resolved=True, events=[ev])


def list_pickups(req: DialogRequest) -> DialogResponse:
    with SessionLocal() as db:
        rows = list(db.scalars(select(Pickup).where(Pickup.user_id == req.user_id, Pickup.status == "pending")
                               .order_by(Pickup.due_date)))
    if not rows:
        return reply(text("📭 No tienes retiros programados. Escribe *farmacia* para programar uno."),
                     state=None, resolved=True)
    lines = [f"• *{p.medication}* — {fmt_date(p.due_date)} en {CENTRO_NOMBRE.get(p.center_id, 'CESFAM')}"
             + (f" (cada {p.freq_days} días)" if p.freq_days else "") for p in rows]
    return reply(text("📋 *Tus próximos retiros*\n\n" + "\n".join(lines)), state=None, resolved=True)


def pickup_answer(pid: int, answer: str, req: DialogRequest) -> DialogResponse:
    with SessionLocal() as db:
        p = db.get(Pickup, pid)
        if not p or p.user_id != req.user_id or p.status != "pending":
            return reply(text("Ese retiro ya estaba registrado. 👍"), state=None)
        done = answer in ("done", "caregiver")
        p.status = "done" if done else "missed"
        nxt = None
        if done and p.freq_days:
            nxt = Pickup(user_id=p.user_id, medication=p.medication, center_id=p.center_id,
                         due_date=p.due_date + timedelta(days=p.freq_days), hour=p.hour, freq_days=p.freq_days)
            db.add(nxt)
        db.commit()
        center, med = p.center_id, p.medication
    ev = DomainEvent(type="pickup_done" if done else "pickup_missed", center=center,
                     props={"by_caregiver": answer == "caregiver"})
    if done:
        body = "✅ ¡Retiro registrado!" + (f" Tu próximo retiro es el *{fmt_date(nxt.due_date)}*." if nxt else "")
        return reply(text(body), state=None, resolved=True, events=[ev])
    msg = lst(f"📝 Registré que no pudiste retirar *{med}*. ¿Qué pasó?",
              [("med:why:stock", "Sin stock"), ("med:why:time", "No tuve tiempo"),
               ("med:why:access", "Problema de traslado"), ("med:why:other", "Otro motivo")], FOOTER, "Responder")
    return reply(msg, state=remember_menu({"step": "why"}, msg), events=[ev])


def handle(req: DialogRequest) -> DialogResponse:
    state = dict(req.state)
    opt = choice(req)

    if opt and opt.startswith("med:pick:"):
        _, _, pid, answer = opt.split(":")
        return pickup_answer(int(pid), answer, req)
    if opt == "med:list" or (req.start and req.intent == "ver_retiros"):
        return list_pickups(req)
    if req.start or opt == "med:start":
        med = (req.entities or {}).get("medicamento")
        return ask_center({"medication": str(med).strip()}) if med else ask_rx()

    step = state.get("step")
    if step == "rx":
        if opt in ("med:rx:yes", "med:rx:unsure"):
            return reply(text("✍️ Escribe el *nombre del medicamento* tal como aparece en tu receta."),
                         state={"step": "drug"})
        if opt == "med:rx:no":
            return reply(text("👍 Entendido. Cuando tengas una receta, escríbeme *farmacia*."), state=None, resolved=True)
        return ask_rx()
    if step == "drug":
        if len(req.text.strip()) < 3:
            return reply(text("✍️ ¿Cuál es el nombre del medicamento?"), state=state)
        return ask_center({"medication": " ".join(req.text.split())[:80]})
    if step == "center" and opt and opt.startswith("med:center:"):
        return availability({**state, "center_id": opt.split(":")[2]})
    if step == "alert":
        if opt == "med:alert:yes":
            with SessionLocal() as db:
                db.add(StockAlert(user_id=req.user_id, center_id=state["center_id"],
                                  key=stock_provider.key(state["medication"]), name=state["medication"]))
                db.commit()
            return reply(text("🔔 Te avisaré apenas el CESFAM registre stock."), state=None, resolved=True,
                         events=[DomainEvent(type="stock_alert_subscribed", center=state["center_id"])])
        return reply(text("👍 Entendido."), state=None, resolved=True)
    if step == "freq" and opt and opt.startswith("med:freq:"):
        return ask_next({**state, "freq": int(opt.split(":")[2])})
    if step == "next":
        if opt and opt.startswith("med:next:"):
            return ask_hour({**state, "next": opt.split(":")[2]})
        d = parse_date(req.text)
        if d and d >= today_local():
            return ask_hour({**state, "next": d.isoformat()})
        return ask_next(state)
    if step == "hour":
        if opt and opt.startswith("med:hour:"):
            return save(req, {**state, "hour": opt.split(":", 2)[2]})
        times = parse_times(req.text)
        return save(req, {**state, "hour": times[0]}) if times else ask_hour(state)
    if step == "link":
        if opt == "med:link:yes":
            return reply(state=None, handoff=Handoff(service="recordatorios", intent="recordatorio_medicamento",
                                                    entities={"medicamento": state["medication"],
                                                              "source": "medicamentos"}))
        return reply(text("👍 Perfecto, mantengo solo el plan de retiro."), state=None, resolved=True)
    if step == "why" and opt and opt.startswith("med:why:"):
        return reply(text("Gracias por contarme. 💙 Si necesitas reprogramar, escribe *farmacia*."), state=None,
                     resolved=True, events=[DomainEvent(type="pickup_missed_reason", props={"reason": opt.split(":")[2]})])
    menu = state.get("_menu")
    if menu:
        return reply(Message(**menu), state=state)
    return ask_rx()
