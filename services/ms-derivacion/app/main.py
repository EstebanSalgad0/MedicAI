from __future__ import annotations

from fastapi import Depends
from sqlalchemy import func, select

from medicai_common import events
from medicai_common.contracts import DialogRequest, DialogResponse
from medicai_common.messages import buttons
from medicai_common.notify import send
from medicai_common.service import create_service, require_internal, setup_logging
from medicai_common.textutil import now_local

from . import derivaciones, dialog
from .models import Derivacion, Referral, SessionLocal, init_db

SERVICE = "derivacion"
log = setup_logging(SERVICE)
app = create_service(SERVICE, "Guía de ruta para pacientes y derivaciones clínicas con seguimiento "
                              "(enviada / agendada / atendida / caducada).", on_startup=init_db)
app.include_router(derivaciones.router)


@app.post("/dialog", response_model=DialogResponse, dependencies=[Depends(require_internal)], tags=["chat"])
def post_dialog(req: DialogRequest) -> DialogResponse:
    return dialog.handle(req)


@app.post("/internal/jobs/tick", dependencies=[Depends(require_internal)], tags=["jobs"])
def tick():
    now = now_local().replace(tzinfo=None)
    sent = 0
    with SessionLocal() as db:
        for ref in db.scalars(select(Referral).where(Referral.status == "open", Referral.followup_sent.is_(False),
                                                     Referral.followup_at <= now)):
            label = {"interconsulta": "tu interconsulta"}.get(ref.doc_type, "tu trámite de salud")
            msg = buttons(f"📋 *Seguimiento*\n\n¿Ya te contactaron por {label}?",
                          [(f"der:fu:{ref.id}:yes", "✅ Sí"), (f"der:fu:{ref.id}:no", "⏳ Aún no")],
                          "Guía de Ruta • MedicAI")
            if send(ref.user_id, [msg]):
                ref.followup_sent = True
                sent += 1
                events.emit("referral_followup_sent", service=SERVICE, user_id=ref.user_id)
        db.commit()
    return {"sent": sent, "caducadas": derivaciones.caducar_vencidas()}


@app.get("/stats", tags=["dashboard"])
def stats():
    with SessionLocal() as db:
        rows = db.execute(select(Referral.doc_type, Referral.status, func.count())
                          .group_by(Referral.doc_type, Referral.status)).all()
        clinicas = dict(db.execute(select(Derivacion.estado, func.count()).group_by(Derivacion.estado)).all())
    return {"referrals": [{"doc_type": d, "status": s, "total": n} for d, s, n in rows],
            "derivaciones": clinicas}
