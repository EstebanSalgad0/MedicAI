"""Resultados de exámenes: identifica al paciente (RUN + fecha de nacimiento) y
muestra solo el ESTADO de cada examen. Nunca valores ni interpretaciones."""
from __future__ import annotations

from datetime import timedelta

from medicai_common import rut
from medicai_common.contracts import DialogRequest, DialogResponse, DomainEvent, reply
from medicai_common.matching import choice
from medicai_common.messages import buttons, text
from medicai_common.textutil import now_local, parse_date

from . import lis
from .models import Patient, ResultWatch, SessionLocal

FOOTER = "Resultados • MedicAI"
VERIFY_HOURS = 24  # la verificación de identidad vale por un día
DONDE = ("🔒 Por tu seguridad no muestro valores ni interpretaciones por este chat.\n"
         "Revísalos en el *portal del paciente con ClaveÚnica* o en *Admisión* con tu cédula, "
         "y conversa los resultados con tu médico.")
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _fecha(dt) -> str:
    return f"{dt.day} {MESES[dt.month - 1]}"


def run_from_id(user_id: str) -> str | None:
    """En modo cuidador el id trae el RUN del paciente: cui:<cuidador>:<RUN>."""
    return user_id.rsplit(":", 1)[1] if user_id.startswith("cui:") else None


def ask_run(state: dict, error: bool = False) -> DialogResponse:
    pre = "😕 Ese RUN no es válido. Revisa el dígito verificador.\n\n" if error else ""
    return reply(text(pre + "📋 *Resultados de exámenes*\n\nPara proteger tu información necesito verificar tu "
                      "identidad.\n✍️ Escribe tu *RUN* (ej: 12.345.678-5):"), state={**state, "step": "run"})


def ask_birth(state: dict, quien: str = "tu", error: bool = False) -> DialogResponse:
    pre = "😕 La fecha no coincide con la registrada.\n\n" if error else ""
    return reply(text(pre + f"🎂 Para confirmar, escribe {quien} *fecha de nacimiento* (dd-mm-aaaa):"),
                 state={**state, "step": "birth"})


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
    para = f" de *{req.name}*" if run_from_id(req.user_id) and req.name else ""
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
    state = dict(req.state)
    opt = choice(req)
    now = now_local().replace(tzinfo=None)
    acting_run = run_from_id(req.user_id)
    quien = f"la de *{req.name}*" if acting_run and req.name else "tu"

    if opt == "res:watch":
        run = state.get("run") or acting_run
        with SessionLocal() as db:
            p = db.get(Patient, req.user_id)
        run = run or (p.run if p else None)
        if not run:
            return ask_run({})
        return watch(req, run)

    step = state.get("step")
    if step == "run":
        run = rut.valid(req.text)
        if not run:
            return ask_run(state, error=True)
        return ask_birth({"run": run}, quien)
    if step == "birth":
        born = parse_date(req.text.strip())
        if not born:
            return ask_birth(state, quien)
        with SessionLocal() as db:
            p = db.get(Patient, req.user_id)
            if p and p.run == state["run"] and p.birth_date != born:
                tries = state.get("tries", 0) + 1
                if tries >= 2:
                    return reply(text("🔒 No pude verificar tu identidad. Por seguridad, consulta tus resultados en "
                                      "Admisión con tu cédula."), state=None)
                return ask_birth({**state, "tries": tries}, quien, error=True)
            if not p:
                p = Patient(user_id=req.user_id, run=state["run"], birth_date=born)
                db.add(p)
            p.run, p.verified_at = state["run"], now
            db.commit()
        return show(req, state["run"])

    # inicio
    with SessionLocal() as db:
        p = db.get(Patient, req.user_id)
    if p and p.verified_at and now - p.verified_at < timedelta(hours=VERIFY_HOURS):
        return show(req, p.run)
    if p:
        return ask_birth({"run": p.run}, quien)
    if acting_run:
        return ask_birth({"run": acting_run}, quien)
    return ask_run({})
