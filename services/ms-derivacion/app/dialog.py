"""Guía de ruta: qué hacer con una interconsulta, orden de exámenes, receta o derivación urgente."""
from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

from medicai_common.contracts import DialogRequest, DialogResponse, DomainEvent, reply
from medicai_common.matching import choice, remember_menu
from medicai_common.messages import Message, buttons, lst, text
from medicai_common.textutil import normalize, now_local

from . import contenidos
from .models import Referral, SessionLocal

FOOTER = "Guía de Ruta • MedicAI"
TIPOS = [
    ("der:type:interconsulta", "📄 Interconsulta", "Derivación a especialista"),
    ("der:type:examenes", "🧾 Orden de exámenes", "Exámenes o procedimientos"),
    ("der:type:receta", "💊 Receta", "Indicación de tratamiento"),
    ("der:type:urgente", "🚨 Derivación urgente", "Te indicaron ir a urgencia"),
    ("der:type:otro", "❓ No estoy seguro/a", "Requisitos generales"),
]
DIRECTORIO = json.loads((Path(__file__).parent / "data" / "establecimientos_urgencia.json").read_text())["comunas"]


def guided(doc_type: str, ges: str | None = None) -> DomainEvent:
    return DomainEvent(type="referral_guided", props={"doc_type": doc_type, "ges": ges})


def follow_buttons(state: dict, body: str) -> DialogResponse:
    msg = buttons(body, [("der:follow:7", "🔔 Seguimiento 7 días"), ("der:done", "No, gracias")], FOOTER)
    return reply(msg, state=remember_menu({**state, "step": "follow"}, msg))


def ask_type() -> DialogResponse:
    msg = lst("🏥 *Guía de Ruta*\n\nTe explico paso a paso qué hacer con tu documento médico.\n"
              "¿Qué te entregaron?", TIPOS, FOOTER, "Ver documentos")
    return reply(msg, state=remember_menu({"step": "type"}, msg))


def on_type(doc: str, state: dict) -> DialogResponse:
    state = {**state, "doc_type": doc}
    if doc == "interconsulta":
        msg = lst("¿Tu interconsulta está cubierta por *GES* (Garantías Explícitas en Salud)?",
                  [("der:ges:si", "Sí, es GES"), ("der:ges:no", "No es GES"), ("der:ges:ns", "No lo sé")],
                  FOOTER, "Responder")
        return reply(msg, state=remember_menu({**state, "step": "ges"}, msg))
    if doc == "examenes":
        msg = buttons("¿Tu examen requiere *ayuno*?", [("der:fast:yes", "Sí / no sé"), ("der:fast:no", "No")], FOOTER)
        return reply(text(contenidos.exams_steps()), msg, state=remember_menu({**state, "step": "fast"}, msg))
    if doc == "receta":
        msg = buttons("💊 *Receta o indicación de tratamiento*\n\n"
                      "Puedo ayudarte a no olvidar tus tomas o a organizar el retiro en la farmacia del CESFAM.",
                      [("rec:new", "⏰ Recordar tomas"), ("med:start", "🏥 Retiro farmacia"), ("der:done", "No, gracias")],
                      FOOTER)
        return reply(msg, state=None, resolved=True, events=[guided("receta")])
    if doc == "urgente":
        msg = buttons("¿Te indico dónde consultar?", [("der:sapu", "📍 Sí, mi comuna"), ("der:done", "No por ahora")], FOOTER)
        return reply(text(contenidos.urgent_referral_steps()), msg,
                     state=remember_menu({**state, "step": "urgent"}, msg), events=[guided("urgente")])
    return follow_buttons(state, contenidos.req_docs_steps())


def register_followup(req: DialogRequest, days: int) -> DialogResponse:
    st = req.state
    with SessionLocal() as db:
        ref = Referral(user_id=req.user_id, doc_type=st.get("doc_type", "otro"), ges=st.get("ges"),
                       followup_at=now_local().replace(tzinfo=None) + timedelta(days=days))
        db.add(ref)
        db.commit()
    return reply(text(f"✅ Listo. En {days} días te preguntaré si ya te contactaron. "
                      "Si tu condición empeora mientras esperas, consulta de nuevo en tu CESFAM."),
                 state=None, resolved=True,
                 events=[guided(st.get("doc_type", "otro"), st.get("ges")),
                         DomainEvent(type="referral_followup_registered", props={"doc_type": st.get("doc_type")})])


def followup_answer(ref_id: int, answer: str, req: DialogRequest) -> DialogResponse:
    with SessionLocal() as db:
        ref = db.get(Referral, ref_id)
        if not ref or ref.user_id != req.user_id:
            return reply(text("No encontré ese trámite."), state=None)
        days_open = (now_local().replace(tzinfo=None) - ref.created_at).days
        if answer == "yes":
            ref.status = "contacted"
            msg = "🙌 ¡Qué bien! Recuerda llevar tu cédula y la interconsulta a la cita."
        else:
            ref.followup_at = now_local().replace(tzinfo=None) + timedelta(days=7)
            ref.followup_sent = False
            msg = ("📌 Te recomiendo acercarte al *SOME* de tu CESFAM con tu número de seguimiento para "
                   "consultar el estado. Volveré a preguntarte en 7 días.")
        db.commit()
    return reply(text(msg), state=None, resolved=True,
                 events=[DomainEvent(type="referral_followup_answer",
                                     props={"contacted": answer == "yes", "days_open": days_open})])


def handle(req: DialogRequest) -> DialogResponse:
    state = dict(req.state)
    opt = choice(req)
    if req.start:
        doc = (req.entities or {}).get("tipo_documento")
        return on_type(doc, {}) if doc in {t[0].split(":")[2] for t in TIPOS} else ask_type()

    if opt and opt.startswith("der:fu:"):
        _, _, ref_id, answer = opt.split(":")
        return followup_answer(int(ref_id), answer, req)
    if opt and opt.startswith("der:type:"):
        return on_type(opt.split(":")[2], {})
    if opt and opt.startswith("der:ges:"):
        ges = opt.split(":")[2]
        state["ges"] = ges
        return follow_buttons(state, contenidos.interconsulta_instructions("Sí, es GES" if ges == "si" else "No")
                              + "\n\n🔔 ¿Quieres que te haga *seguimiento* en 7 días?")
    if opt and opt.startswith("der:fast:"):
        tip = ("💡 Muchos exámenes de sangre (glicemia, colesterol, triglicéridos) requieren *8 a 12 horas* de ayuno. "
               "Confírmalo en tu orden o en el SOME." if opt.endswith("yes")
               else "👍 Si tienes dudas, confírmalo al agendar en el SOME o laboratorio.")
        return reply(text(tip), state=None, resolved=True, events=[guided("examenes")])
    if opt and opt.startswith("der:follow:"):
        return register_followup(req, int(opt.split(":")[2]))
    if opt == "der:sapu":
        return reply(text("📍 ¿En qué *comuna* estás?"), state={**state, "step": "comuna", "_menu": None})
    if opt == "der:done":
        return reply(text("👍 Entendido. Si necesitas volver a la guía, escribe *guía de ruta*."), state=None,
                     resolved=True, events=[guided(state.get("doc_type", "otro"), state.get("ges"))])

    step = state.get("step")
    if step == "comuna":
        lugares = DIRECTORIO.get(normalize(req.text).strip(), [])
        if lugares:
            body = "🏥 *Atención de urgencia en tu comuna:*\n\n" + "\n\n".join(
                f"*{p['nombre']}*\n{p.get('direccion', '')}\n{p.get('horario', '')}" for p in lugares)
        else:
            body = ("Aún no tengo el directorio de urgencias de esa comuna. Llama a *Salud Responde 600 360 7777* "
                    "(24 h) para que te indiquen el SAPU o SAR más cercano. Si es grave, llama al *131*.")
        return reply(text(body), state=None, resolved=True)
    if step in ("type", None):
        return ask_type()
    menu = state.get("_menu")
    if menu:
        return reply(Message(**menu), state=state)
    return ask_type()
