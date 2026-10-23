from __future__ import annotations

import os
from datetime import timedelta

from fastapi import Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from medicai_common import events
from medicai_common.centros import CENTRO_NOMBRE, ESTABLECIMIENTOS
from medicai_common.contracts import DialogRequest, DialogResponse
from medicai_common.messages import buttons, text
from medicai_common.notify import send
from medicai_common.service import create_service, require_internal, setup_logging
from medicai_common.textutil import now_local

from . import dialog, stock_provider
from .models import Pickup, SessionLocal, StockAlert, StockItem, init_db

SERVICE = "medicamentos"
log = setup_logging(SERVICE)

DEMO_STOCK = [  # inventario de demostración (SEED_DEMO_STOCK=true)
    ("Paracetamol 500 mg", 120), ("Losartán 50 mg", 80), ("Metformina 850 mg", 95),
    ("Atorvastatina 20 mg", 40), ("Enalapril 10 mg", 6), ("Amoxicilina 500 mg", 4),
    ("Salbutamol inhalador", 0), ("Levotiroxina 100 mcg", 25),
]


def _startup() -> None:
    init_db()
    if os.getenv("SEED_DEMO_STOCK", "false").lower() == "true":
        with SessionLocal() as db:
            seeded = set(db.scalars(select(StockItem.center_id).distinct()))
            nuevos = [c for c, _, _ in ESTABLECIMIENTOS if c not in seeded]
            for center_id in nuevos:  # también la Farmacia Hospitalaria en instalaciones existentes
                for name, qty in DEMO_STOCK:
                    db.add(StockItem(center_id=center_id, key=stock_provider.key(name), name=name, stock=qty))
            db.commit()
            if nuevos:
                log.info("Inventario de demostración cargado: %s", nuevos)


app = create_service(SERVICE, "Disponibilidad de fármacos, retiros programados en farmacia del CESFAM "
                              "y avisos de reposición de stock.", on_startup=_startup)


@app.post("/dialog", response_model=DialogResponse, dependencies=[Depends(require_internal)], tags=["chat"])
def post_dialog(req: DialogRequest) -> DialogResponse:
    return dialog.handle(req)


# ---------- API para el dashboard ----------

class StockIn(BaseModel):
    center_id: str
    name: str
    stock: int = Field(ge=0)
    min_stock: int = Field(default=10, ge=0)


@app.get("/stock", tags=["dashboard"])
def list_stock(center_id: str | None = None):
    q = select(StockItem).order_by(StockItem.center_id, StockItem.name)
    if center_id:
        q = q.where(StockItem.center_id == center_id)
    with SessionLocal() as db:
        return [{"id": s.id, "center_id": s.center_id, "center_nombre": CENTRO_NOMBRE.get(s.center_id, s.center_id),
                 "name": s.name, "stock": s.stock, "min_stock": s.min_stock,
                 "status": "none" if s.stock <= 0 else "low" if s.stock < s.min_stock else "available",
                 "updated_at": s.updated_at} for s in db.scalars(q)]


@app.put("/stock", tags=["dashboard"])
def upsert_stock(body: StockIn):
    """Actualiza inventario. Si un fármaco vuelve a tener stock, avisa a quienes lo pidieron."""
    k = stock_provider.key(body.name)
    notified = 0
    with SessionLocal() as db:
        item = db.scalar(select(StockItem).where(StockItem.center_id == body.center_id, StockItem.key == k))
        was_empty = item is None or item.stock <= 0
        if item:
            item.stock, item.min_stock = body.stock, body.min_stock
        else:
            item = StockItem(center_id=body.center_id, key=k, name=body.name, stock=body.stock,
                             min_stock=body.min_stock)
            db.add(item)
        if was_empty and body.stock > 0:
            for a in db.scalars(select(StockAlert).where(StockAlert.center_id == body.center_id,
                                                         StockAlert.key == k, StockAlert.notified.is_(False))):
                if send(a.user_id, [text(f"🔔 ¡Buenas noticias! Ya hay stock de *{a.name}* en "
                                         f"{CENTRO_NOMBRE.get(a.center_id, 'tu CESFAM')}.")]):
                    a.notified = True
                    notified += 1
        db.commit()
    if notified:
        events.emit("stock_alert_notified", service=SERVICE, center=body.center_id, props={"patients": notified})
    return {"ok": True, "notified": notified}


@app.get("/pickups", tags=["dashboard"])
def list_pickups(status: str | None = None, center_id: str | None = None, limit: int = 300):
    q = select(Pickup).order_by(Pickup.due_date)
    if status:
        q = q.where(Pickup.status == status)
    if center_id:
        q = q.where(Pickup.center_id == center_id)
    with SessionLocal() as db:
        return [{"id": p.id, "medication": p.medication, "center_id": p.center_id,
                 "center_nombre": CENTRO_NOMBRE.get(p.center_id, p.center_id), "due_date": p.due_date,
                 "freq_days": p.freq_days, "status": p.status} for p in db.scalars(q.limit(min(limit, 1000)))]


@app.get("/stats", tags=["dashboard"])
def stats():
    with SessionLocal() as db:
        by_status = dict(db.execute(select(Pickup.status, func.count()).group_by(Pickup.status)).all())
        low = db.scalar(select(func.count()).select_from(StockItem).where(StockItem.stock < StockItem.min_stock))
        alerts = db.scalar(select(func.count()).select_from(StockAlert).where(StockAlert.notified.is_(False)))
    closed = by_status.get("done", 0) + by_status.get("missed", 0)
    return {"pickups": by_status, "pickup_rate": round(by_status.get("done", 0) / closed, 4) if closed else None,
            "low_stock_items": low, "pending_stock_alerts": alerts}


# ---------- tareas programadas ----------

@app.post("/internal/jobs/tick", dependencies=[Depends(require_internal)], tags=["jobs"])
def tick():
    now = now_local().replace(tzinfo=None)
    today, hhmm = now.date(), now.strftime("%H:%M")
    counts = {"before": 0, "day": 0, "missed": 0}
    with SessionLocal() as db:
        for p in db.scalars(select(Pickup).where(Pickup.status == "pending")):
            center = CENTRO_NOMBRE.get(p.center_id, "tu CESFAM")
            if not p.notified_before and p.due_date - today == timedelta(days=3) and hhmm >= p.hour:
                if send(p.user_id, [text(f"📢 En 3 días ({dialog.fmt_date(p.due_date)}) te toca retirar "
                                         f"*{p.medication}* en {center}.")]):
                    p.notified_before = True
                    counts["before"] += 1
            if not p.notified_day and p.due_date == today and hhmm >= p.hour:
                msg = buttons(f"💊 *Hoy te toca retirar {p.medication}* en {center}.\n\n¿Pudiste retirarlo?",
                              [(f"med:pick:{p.id}:done", "✅ Sí, lo retiré"),
                               (f"med:pick:{p.id}:caregiver", "👥 Lo retiró otra persona"),
                               (f"med:pick:{p.id}:missed", "❌ No pude")], "Farmacia • MedicAI")
                if send(p.user_id, [msg]):
                    p.notified_day = True
                    counts["day"] += 1
            if (today - p.due_date).days >= 7:
                p.status = "missed"
                counts["missed"] += 1
                events.emit("pickup_missed", service=SERVICE, user_id=p.user_id, center=p.center_id,
                            props={"auto": True})
                send(p.user_id, [text(f"⚠️ No registraste el retiro de *{p.medication}*. "
                                      "Si lo necesitas, escribe *farmacia* para reprogramarlo.")])
        db.commit()
    return counts
