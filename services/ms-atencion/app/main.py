from __future__ import annotations

from typing import Literal

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from medicai_common import events
from medicai_common.contracts import DialogRequest, DialogResponse
from medicai_common.messages import text
from medicai_common.notify import send
from medicai_common.service import create_service, require_internal, setup_logging
from medicai_common.textutil import now_local

from . import dialog
from .models import Caregiver, SessionLocal, Ticket, init_db

SERVICE = "atencion"
log = setup_logging(SERVICE)
app = create_service(SERVICE, "Trámites FONASA, información del hospital, derivación a una persona con contexto "
                              "y modo cuidador.", on_startup=init_db)


@app.post("/dialog", response_model=DialogResponse, dependencies=[Depends(require_internal)], tags=["chat"])
def post_dialog(req: DialogRequest) -> DialogResponse:
    return dialog.handle(req)


# ---------- bandeja de solicitudes para funcionarios ----------

def _ticket(t: Ticket) -> dict:
    return {"id": t.id, "folio": f"#{t.id:05d}", "name": t.name, "channel": t.channel, "topic": t.topic,
            "topic_nombre": dialog.TEMA_NOMBRE.get(t.topic, t.topic), "summary": t.summary,
            "transcript": t.transcript or [], "replies": t.replies or [], "acting_for": t.acting_for,
            "in_hours": t.in_hours, "status": t.status, "created_at": t.created_at, "updated_at": t.updated_at}


@app.get("/tickets", tags=["dashboard"])
def list_tickets(status: str | None = None, limit: int = 100):
    q = select(Ticket).order_by(Ticket.created_at.desc()).limit(min(limit, 500))
    if status:
        q = q.where(Ticket.status == status)
    with SessionLocal() as db:
        items = [_ticket(t) for t in db.scalars(q)]
        counts = dict(db.execute(select(Ticket.status, func.count()).group_by(Ticket.status)).all())
    return {"items": items, "counts": counts}


class ReplyIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    agent: str = "Mesa de ayuda"


@app.post("/tickets/{ticket_id}/reply", tags=["dashboard"])
def reply_ticket(ticket_id: int, body: ReplyIn):
    """El funcionario responde por el mismo canal del paciente (WhatsApp o simulador)."""
    with SessionLocal() as db:
        t = db.get(Ticket, ticket_id)
        if not t:
            raise HTTPException(404, "Solicitud no encontrada")
        ok = send(t.user_id, [text(f"🧑‍💼 *{body.agent} (Hospital Regional de Talca)*\n\n{body.text}\n\n"
                                   "_Si necesitas responder, escribe *hablar con una persona*._")])
        if not ok:
            raise HTTPException(502, "No se pudo enviar el mensaje al paciente")
        t.replies = (t.replies or []) + [{"at": now_local().replace(tzinfo=None).isoformat(timespec="minutes"),
                                          "agent": body.agent, "text": body.text}]
        t.status = "answered"
        db.commit()
        out = _ticket(t)
    events.emit("handoff_answered", service=SERVICE, user_id=t.user_id, props={"topic": t.topic})
    return out


class StatusIn(BaseModel):
    status: Literal["open", "answered", "closed"]


@app.patch("/tickets/{ticket_id}", tags=["dashboard"])
def update_ticket(ticket_id: int, body: StatusIn):
    with SessionLocal() as db:
        t = db.get(Ticket, ticket_id)
        if not t:
            raise HTTPException(404, "Solicitud no encontrada")
        t.status = body.status
        db.commit()
        return _ticket(t)


class CaregiverIn(BaseModel):
    caregiver_id: str = Field(min_length=1, max_length=120)
    caregiver_name: str = Field(min_length=1, max_length=120)
    caregiver_run: str = Field(min_length=3, max_length=12)
    patient_name: str = Field(min_length=3, max_length=120)
    patient_run: str = Field(min_length=3, max_length=12)
    relationship: str = Field(min_length=2, max_length=30)


@app.post("/internal/caregivers", dependencies=[Depends(require_internal)], tags=["interno"])
def create_caregiver(body: CaregiverIn):
    """Lo llama ms-identidad cuando el cuidador completa el registro tras ingresar con ClaveÚnica."""
    with SessionLocal() as db:
        c = Caregiver(**body.model_dump())
        db.add(c)
        db.commit()
        cid = c.id
    events.emit("caregiver_registered", service=SERVICE, user_id=body.caregiver_id,
                props={"relationship": body.relationship, "verificado": "claveunica"})
    return {"id": cid}


@app.get("/caregivers/stats", tags=["dashboard"])
def caregiver_stats():
    with SessionLocal() as db:
        active = db.scalar(select(func.count()).select_from(Caregiver).where(Caregiver.active.is_(True)))
    return {"active": active}
