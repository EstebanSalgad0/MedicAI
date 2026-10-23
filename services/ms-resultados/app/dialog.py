"""Resultados de exámenes: muestra solo el ESTADO de cada examen, nunca valores ni
interpretaciones.

La identidad del paciente se verifica con ClaveÚnica fuera del chat (ms-identidad): el
chat nunca pide RUN, fecha de nacimiento, claves ni datos de pago.
"""
from __future__ import annotations

import os

from medicai_common import identidad, rut
from medicai_common.contracts import DialogRequest, DialogResponse, DomainEvent, reply
from medicai_common.matching import choice
from medicai_common.messages import buttons, text
from medicai_common.textutil import now_local

from . import lis
from .models import ResultWatch, SessionLocal

FOOTER = "Resultados • MedicAI"
# La verificación con ClaveÚnica vale por un día para ver resultados
VERIFY_HOURS = float(os.getenv("RESULTADOS_VERIFICACION_HORAS", "24"))
DONDE = ("🔒 Por tu seguridad no muestro valores ni interpretaciones por este chat.\n"
         "Revísalos en el *portal del paciente con ClaveÚnica* o en *Admisión* con tu cédula, "
         "y conversa los resultados con tu médico.")
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _fecha(dt) -> str:
    return f"{dt.day} {MESES[dt.month - 1]}"


def show(req: DialogRequest, run: str) -> DialogResponse:
    now = now_local().replace(tzinfo=None)
    exams = lis.exams_for(run, now.date())
    lines, pending = [], []
    for e in sorted(exams, key=lambda x: x.ready_at, reverse=True):
        if e.status(now) == "disponible":
            lines.append(f"✅ *{e.name}* ({e.area}) — disponible desde el {_fecha(e.ready_at)}")
        else:
            cuando = f"hoy cerca de las {e.ready_at:%H:%M}" if e.ready_at.date() == now.date() \
                else f"el {_fecha(e.ready_at)}"
            lines.append(f"⏳ *{e.name}* ({e.area}) — en proceso, estimado {cuando}")
            pending.append(e)
    para = f" de *{req.name}*" if identidad.run_en_modo_cuidador(req.user_id) and req.name else ""
    body = f"📋 *Exámenes{para}* ({rut.mask(run)})\n\n" + "\n".join(lines) + f"\n\n{DONDE}"
    opts = [("res:watch", "🔔 Avisarme")] if pending else []
    opts.append(("agd:start", "📅 Agendar control"))
    ev = DomainEvent(type="results_checked", props={"available": len(exams) - len(pending), "pending": len(pending)})
    return reply(buttons(body, opts, FOOTER), state=None, resolved=True, events=[ev])


def watch(req: DialogRequest, run: str) -> DialogResponse:
    now = now_local().replace(tzinfo=None)
    pending = [e for e in lis.exams_for(run, now.date()) if e.status(now) == "en_proceso"]
    with SessionLocal() as db:
        for e in pending:
            exists = db.query(ResultWatch).filter_by(user_id=req.user_id, exam=e.name, notified_at=None).first()
            if not exists:
                db.add(ResultWatch(user_id=req.user_id, run=run, exam=e.name, ready_at=e.ready_at))
        db.commit()
    nombres = ", ".join(e.name for e in pending) or "tus exámenes"
    return reply(text(f"🔔 Listo. Te aviso por este chat apenas el médico valide: *{nombres}*."),
                 state=None, resolved=True, events=[DomainEvent(type="result_watch", props={"exams": len(pending)})])


def handle(req: DialogRequest) -> DialogResponse:
    opt = choice(req)
    run = identidad.run_verificado(req.user_id, max_horas=VERIFY_HOURS)
    if not run:
        para = f"ver los exámenes de {req.name}" if identidad.run_en_modo_cuidador(req.user_id) else "ver tus exámenes"
        return reply(identidad.pedir_claveunica(req.user_id, "resultados", para, FOOTER), state=None,
                     events=[DomainEvent(type="identity_requested", props={"proposito": "resultados"})])
    if opt == "res:watch":
        return watch(req, run)
    return show(req, run)
