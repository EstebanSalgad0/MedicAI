from __future__ import annotations

from fastapi import Depends
from sqlalchemy import func, select

from medicai_common import events
from medicai_common.contracts import DialogRequest, DialogResponse
from medicai_common.messages import buttons
from medicai_common.notify import send
from medicai_common.service import create_service, require_internal, setup_logging
from medicai_common.textutil import now_local

from . import dialog
from .models import ResultWatch, SessionLocal, init_db

SERVICE = "resultados"
log = setup_logging(SERVICE)
app = create_service(SERVICE, "Estado de exámenes de laboratorio e imagenología, con aviso automático cuando el "
                              "resultado se valida. Nunca entrega valores ni interpretaciones.", on_startup=init_db)


@app.post("/dialog", response_model=DialogResponse, dependencies=[Depends(require_internal)], tags=["chat"])
def post_dialog(req: DialogRequest) -> DialogResponse:
    return dialog.handle(req)


@app.post("/internal/jobs/tick", dependencies=[Depends(require_internal)], tags=["jobs"])
def tick():
    """Avisa los resultados recién validados (meta: menos de 5 minutos)."""
    now = now_local().replace(tzinfo=None)
    sent = 0
    with SessionLocal() as db:
        for w in db.scalars(select(ResultWatch).where(ResultWatch.notified_at.is_(None), ResultWatch.ready_at <= now)):
            msg = buttons(f"📋 *Tu resultado de {w.exam} ya está disponible.*\n\n{dialog.DONDE}",
                          [("res:start", "📋 Ver mis exámenes"), ("agd:start", "📅 Agendar control")],
                          dialog.FOOTER)
            if send(w.user_id, [msg]):
                w.notified_at = now
                sent += 1
                events.emit("result_notified", service=SERVICE, user_id=w.user_id,
                            props={"delay_s": round((now - w.ready_at).total_seconds())})
        db.commit()
    return {"notified": sent}


@app.get("/stats", tags=["dashboard"])
def stats():
    with SessionLocal() as db:
        pending = db.scalar(select(func.count()).select_from(ResultWatch).where(ResultWatch.notified_at.is_(None)))
        done = list(db.execute(select(ResultWatch.ready_at, ResultWatch.notified_at)
                               .where(ResultWatch.notified_at.is_not(None))))
    delays = sorted((n - r).total_seconds() for r, n in done)
    within = sum(1 for d in delays if d <= 300)
    return {"pending": pending, "notified": len(delays),
            "within_5_min_rate": round(within / len(delays), 4) if delays else None,
            "p95_delay_s": delays[int(0.95 * (len(delays) - 1))] if delays else None}
