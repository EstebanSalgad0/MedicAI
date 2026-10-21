"""Atención al usuario: trámites FONASA, información práctica del hospital, contacto con
una persona (con contexto) y modo cuidador."""
from __future__ import annotations

from medicai_common import hospital, rut
from medicai_common.contracts import DialogRequest, DialogResponse, DomainEvent, reply
from medicai_common.matching import choice, remember_menu
from medicai_common.messages import buttons, lst, text
from medicai_common.textutil import now_local

from . import contenidos
from .models import Caregiver, SessionLocal, Ticket

FOOTER = "Atención • MedicAI"
TEMAS = [("agenda", "📅 Horas y agenda"), ("resultados", "📋 Resultados"), ("fonasa", "💳 FONASA"),
         ("reclamo", "📣 Reclamo"), ("sugerencia", "💡 Sugerencia"), ("otro", "❓ Otro tema")]
TEMA_NOMBRE = {k: v.split(" ", 1)[1] for k, v in TEMAS} | {"saludmental": "Salud mental"}
RELACIONES = [("hijo", "Hijo/a"), ("pareja", "Cónyuge o pareja"), ("padre", "Madre o padre"),
              ("hermano", "Hermano/a"), ("otro", "Otro familiar o cuidador")]


def in_office_hours() -> bool:
    now = now_local()
    return now.weekday() < 5 and 8 <= now.hour < 17


# ---------- FONASA e información ----------

def fonasa_menu() -> DialogResponse:
    msg = lst("💳 *Trámites FONASA*\n\n¿Con qué te ayudo?",
              [(f"ate:fonasa:{k}", v[0]) for k, v in contenidos.FONASA.items()]
              + [("ate:humano:fonasa", "💬 Ejecutivo FONASA")], FOOTER, "Ver trámites")
    return reply(msg, state=remember_menu({"step": "fonasa"}, msg))


def fonasa_item(key: str) -> DialogResponse:
    _, body = contenidos.FONASA[key]
    msg = buttons(body + contenidos.GUIA, [("ate:fonasa", "💳 Otro trámite"), ("ate:humano:fonasa", "💬 Ejecutivo")],
                  FOOTER)
    return reply(msg, state=None, resolved=True, events=[DomainEvent(type="info_viewed", props={"tema": f"fonasa_{key}"})])


def info(key: str) -> DialogResponse:
    if key == "visitas":
        body, opts = contenidos.VISITAS, [("ate:info", "🏥 Info del hospital")]
    elif key == "prep":
        body, opts = contenidos.PREPARACION, [("agd:start", "📅 Agendar una hora")]
    else:
        body, opts = contenidos.INFO, [("ate:visitas", "👥 Visitas"), ("ate:prep", "🧪 Preparar exámenes")]
    return reply(buttons(body, opts, FOOTER), state=None, resolved=True,
                 events=[DomainEvent(type="info_viewed", props={"tema": key})])


# ---------- hablar con una persona ----------

def ask_topic() -> DialogResponse:
    msg = lst("💬 *Hablar con una persona*\n\nTe conecto con la mesa de ayuda del hospital. ¿Sobre qué tema es?",
              [(f"ate:humano:{k}", v) for k, v in TEMAS], FOOTER, "Elegir tema")
    return reply(msg, state=remember_menu({"step": "topic"}, msg))


def ask_summary(topic: str) -> DialogResponse:
    extra = "\n_Tu reclamo se registrará y derivará a la OIRS del hospital._" if topic == "reclamo" else ""
    return reply(text(f"✍️ Cuéntame en una o dos frases qué necesitas sobre *{TEMA_NOMBRE.get(topic, topic)}*."
                      + extra), state={"step": "summary", "topic": topic})


def create_ticket(req: DialogRequest, topic: str, summary: str) -> DialogResponse:
    ents = req.entities or {}
    acting = ents.get("acting") or {}
    horario = in_office_hours()
    with SessionLocal() as db:
        t = Ticket(user_id=req.user_id, channel=req.channel, name=req.name, topic=topic, summary=summary[:1000],
                   transcript=list(ents.get("transcript") or [])[-16:], acting_for=acting.get("name"), in_hours=horario)
        db.add(t)
        db.commit()
        tid = t.id
    folio = f"#{tid:05d}"
    if horario:
        body = (f"✅ Listo. Tu solicitud *{folio}* llegó a la mesa de ayuda *con el resumen de esta conversación*: "
                "no tendrás que repetir todo.\n\nUn funcionario te responderá por este mismo chat.\n"
                f"Si prefieres llamar: 📞 *{hospital.MESA_AYUDA}* ({hospital.MESA_HORARIO}).")
    else:
        body = (f"🌙 Ahora estamos fuera del horario de atención ({hospital.MESA_HORARIO}).\n\n"
                f"Tomé tu solicitud *{folio}* con el resumen de esta conversación y te contactaremos el próximo día "
                f"hábil. También puedes llamar a la mesa de ayuda: 📞 *{hospital.MESA_AYUDA}*.")
    if topic == "reclamo":
        body += "\n\n📣 Tu reclamo será derivado a la *OIRS*, que debe responderte formalmente."
    return reply(text(body), state=None, resolved=True,
                 events=[DomainEvent(type="handoff_requested", props={"topic": topic, "in_hours": horario,
                                                                      "ticket_id": tid})])


# ---------- modo cuidador ----------

def my_patients(caregiver_id: str) -> list[Caregiver]:
    with SessionLocal() as db:
        return list(db.query(Caregiver).filter_by(caregiver_id=caregiver_id, active=True).order_by(Caregiver.id))


def cuidador_menu(req: DialogRequest) -> DialogResponse:
    pacientes = my_patients(req.user_id)
    intro = ("👪 *Modo cuidador*\n\nPermite gestionar las *horas, resultados y recordatorios* de una persona a tu "
             "cargo (por ejemplo, tu papá o tu mamá), con su autorización.")
    if not pacientes:
        msg = buttons(intro + "\n\nAún no tienes a nadie registrado.", [("ate:cui:new", "➕ Registrar persona")], FOOTER)
        return reply(msg, state=remember_menu({"step": "cui"}, msg))
    opts = [(f"ate:cui:act:{p.id}", f"👤 {p.patient_name}"[:24], f"{p.relationship} · {rut.mask(p.patient_run)}")
            for p in pacientes[:7]]
    opts += [("ate:cui:new", "➕ Registrar a otra"), ("ate:cui:del", "🗑️ Quitar a alguien")]
    msg = lst(intro + "\n\n¿A quién quieres gestionar?", opts, FOOTER, "Elegir persona")
    return reply(msg, state=remember_menu({"step": "cui"}, msg))


def acting_menu(p: Caregiver) -> DialogResponse:
    msg = lst(f"👤 Ahora gestionas los trámites de *{p.patient_name}*.\n"
              "Lo que hagas quedará a su nombre y los avisos te llegarán a ti.\n\n¿Qué necesitas?",
              [("agd:start", "📅 Agendar una hora"), ("agd:mine", "🔁 Sus horas"), ("res:start", "📋 Sus resultados"),
               ("rec:start", "💊 Sus medicamentos"), ("ate:cui:exit", "↩️ Volver a mi cuenta")], FOOTER, "Ver opciones")
    return reply(msg, state=None, resolved=True,
                 acting={"id": f"cui:{p.caregiver_id}:{p.patient_run}", "name": p.patient_name},
                 events=[DomainEvent(type="caregiver_acting", props={"relationship": p.relationship})])


REG_STEPS = {
    "c_name": "✍️ Primero tus datos. ¿Cuál es tu *nombre completo*?",
    "c_run": "✍️ ¿Cuál es tu *RUN*? (ej: 12.345.678-5)",
    "p_name": "✍️ Ahora la persona a tu cargo. ¿Cuál es su *nombre completo*?",
    "p_run": "✍️ ¿Cuál es su *RUN*?",
}


def ask_reg(state: dict, step: str, error: str = "") -> DialogResponse:
    if step == "rel":
        msg = lst(f"¿Qué relación tienes con *{state['p_name']}*?", [(f"ate:cui:rel:{k}", v) for k, v in RELACIONES],
                  FOOTER, "Elegir")
        return reply(msg, state=remember_menu({**state, "step": "rel"}, msg))
    if step == "confirm":
        msg = buttons(f"📋 *Confirma el registro*\n\n👤 Cuidador/a: {state['c_name']} ({rut.mask(state['c_run'])})\n"
                      f"🧓 Paciente: {state['p_name']} ({rut.mask(state['p_run'])})\n"
                      f"🔗 Relación: {dict(RELACIONES)[state['rel']]}\n\n"
                      f"Declaro que *{state['p_name']}* me autorizó a gestionar sus horas, resultados y "
                      "recordatorios. Puede revocar esta autorización cuando quiera en *Admisión*.",
                      [("ate:cui:save:yes", "✅ Sí, registrar"), ("ate:cui:save:no", "❌ Cancelar")], FOOTER)
        return reply(msg, state=remember_menu({**state, "step": "confirm"}, msg))
    return reply(text((f"😕 {error}\n\n" if error else "") + REG_STEPS[step]), state={**state, "step": step})


def register(req: DialogRequest, state: dict) -> DialogResponse:
    with SessionLocal() as db:
        p = Caregiver(caregiver_id=req.user_id, caregiver_name=state["c_name"], caregiver_run=state["c_run"],
                      patient_name=state["p_name"], patient_run=state["p_run"],
                      relationship=dict(RELACIONES)[state["rel"]])
        db.add(p)
        db.commit()
        pid, name = p.id, p.patient_name
    msg = buttons(f"✅ Listo, quedaste registrado/a como cuidador/a de *{name}*.\n\n"
                  f"{name} puede revocar esta autorización en cualquier momento en Admisión.",
                  [(f"ate:cui:act:{pid}", f"👤 Gestionar ahora")], FOOTER)
    return reply(msg, state=None, resolved=True,
                 events=[DomainEvent(type="caregiver_registered", props={"relationship": state["rel"]})])


def cuidador(req: DialogRequest, parts: list[str], state: dict) -> DialogResponse:
    action = parts[2] if len(parts) > 2 else ""
    acting = (req.entities or {}).get("acting") or {}
    if action == "new":
        return ask_reg({}, "c_name")
    if action == "act":
        with SessionLocal() as db:
            p = db.get(Caregiver, int(parts[3]))
        if not p or p.caregiver_id != req.user_id or not p.active:
            return reply(text("No encontré esa autorización."), state=None)
        return acting_menu(p)
    if action == "exit":
        return reply(text("↩️ Volviste a tu cuenta. Lo que hagas ahora será a tu nombre."), state=None,
                     resolved=True, acting={})
    if action == "del":
        pacientes = my_patients(req.user_id)
        if not pacientes:
            return cuidador_menu(req)
        msg = lst("¿A quién quieres quitar de tu modo cuidador?",
                  [(f"ate:cui:rm:{p.id}", f"🗑️ {p.patient_name}"[:24]) for p in pacientes[:9]], FOOTER, "Elegir")
        return reply(msg, state=remember_menu({"step": "cui"}, msg))
    if action == "rm":
        with SessionLocal() as db:
            p = db.get(Caregiver, int(parts[3]))
            if not p or p.caregiver_id != req.user_id:
                return reply(text("No encontré esa autorización."), state=None)
            p.active, p.revoked_at = False, now_local().replace(tzinfo=None)
            db.commit()
            run, name = p.patient_run, p.patient_name
        salir = {} if acting.get("id", "").endswith(f":{run}") else None
        return reply(text(f"🗑️ Ya no gestionas los trámites de *{name}*."), state=None, resolved=True, acting=salir)
    if action == "rel" and state.get("step") == "rel":
        return ask_reg({**state, "rel": parts[3]}, "confirm")
    if action == "save" and state.get("step") == "confirm":
        if parts[3] == "yes":
            return register(req, state)
        return reply(text("👍 No registré a nadie."), state=None)
    return cuidador_menu(req)


def registration_text(req: DialogRequest, state: dict) -> DialogResponse:
    step, val = state["step"], " ".join(req.text.split())
    if step == "c_name":
        return ask_reg({**state, "c_name": val[:120]}, "c_run") if len(val) >= 3 else ask_reg(state, step)
    if step == "c_run":
        run = rut.valid(val)
        return ask_reg({**state, "c_run": run}, "p_name") if run else ask_reg(state, step, "Ese RUN no es válido.")
    if step == "p_name":
        return ask_reg({**state, "p_name": val[:120]}, "p_run") if len(val) >= 3 else ask_reg(state, step)
    if step == "p_run":
        run = rut.valid(val)
        if not run:
            return ask_reg(state, step, "Ese RUN no es válido.")
        if run == state["c_run"]:
            return ask_reg(state, step, "El RUN del paciente debe ser distinto al tuyo.")
        return ask_reg({**state, "p_run": run}, "rel")
    return ask_reg(state, step)


# ---------- punto de entrada ----------

INTENT_ENTRY = {"tramites_fonasa": "ate:fonasa", "modo_cuidador": "ate:cui", "hablar_persona": "ate:humano",
                "info_hospital": "ate:info", "visitas": "ate:visitas", "preparacion_examenes": "ate:prep"}


def handle(req: DialogRequest) -> DialogResponse:
    state = dict(req.state)
    opt = choice(req)
    if req.start and not opt:
        opt = INTENT_ENTRY.get(req.intent or "", "ate:humano")
    if opt and opt.startswith("ate:"):
        parts = opt.split(":")
        kind = parts[1]
        if kind == "fonasa":
            return fonasa_item(parts[2]) if len(parts) > 2 and parts[2] in contenidos.FONASA else fonasa_menu()
        if kind in ("info", "visitas", "prep"):
            return info(kind)
        if kind == "humano":
            return ask_summary(parts[2]) if len(parts) > 2 else ask_topic()
        if kind == "cui":
            return cuidador(req, parts, state)
    step = state.get("step")
    if step == "summary" and req.text.strip():
        return create_ticket(req, state["topic"], req.text.strip())
    if step in REG_STEPS:
        return registration_text(req, state)
    if step == "fonasa":
        return fonasa_menu()
    if step == "topic":
        return ask_topic()
    return cuidador_menu(req) if step in ("cui", "rel", "confirm") else ask_topic()
