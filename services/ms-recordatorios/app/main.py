from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import Depends
from sqlalchemy import func, select

from medicai_common import events
from medicai_common.contracts import DialogRequest, DialogResponse
from medicai_common.messages import buttons
from medicai_common.notify import send
from medicai_common.service import create_service, require_internal, setup_logging
from medicai_common.textutil import now_local

from . import dialog
from .models import DoseLog, Reminder, SessionLocal, init_db

SERVICE = "recordatorios"
log = setup_logging(SERVICE)
app = create_service(SERVICE, "Recordatorios de toma de medicamentos con confirmación de cada dosis "
                              "(indicador de adherencia terapéutica).", on_startup=init_db)

SEND_WINDOW_MIN = 60      # una toma se avisa si el scheduler la detecta dentro de esta ventana
EXPIRE_AFTER_HOURS = 6    # sin respuesta en este plazo -> 'expired'


@app.post("/dialog", response_model=DialogResponse, dependencies=[Depends(require_internal)], tags=["chat"])
def post_dialog(req: DialogRequest) -> DialogResponse:
    return dialog.handle(req)


def _dose_message(log_id: int, medication: str, slot: str):
    return buttons(f"⏰ *Hora de tu medicamento*\n\nSon las {slot}: toca tomar *{medication}*.",
                   [(f"rec:dose:{log_id}:taken", "✅ Ya la tomé"), (f"rec:dose:{log_id}:snooze", "⏰ En 30 min"),
                    (f"rec:dose:{log_id}:skip", "❌ La omití")], "Adherencia • MedicAI")


@app.post("/internal/jobs/tick", dependencies=[Depends(require_internal)], tags=["jobs"])
def tick():
    now = now_local().replace(tzinfo=None, second=0, microsecond=0)
    today = now.date()
    sent = resent = expired = 0
    with SessionLocal() as db:
        # 1) tomas que vencen ahora
        for r in db.scalars(select(Reminder).where(Reminder.active.is_(True))):
            for slot in r.time_list:
                hh, mm = map(int, slot.split(":"))
                slot_dt = datetime(today.year, today.month, today.day, hh, mm)
                if not (slot_dt <= now < slot_dt + timedelta(minutes=SEND_WINDOW_MIN)):
                    continue
                exists = db.scalar(select(DoseLog.id).where(DoseLog.reminder_id == r.id,
                                                            DoseLog.scheduled_date == today, DoseLog.slot == slot))
                if exists:
                    continue
                dl = DoseLog(reminder_id=r.id, user_id=r.user_id, scheduled_date=today, slot=slot, sent_at=now)
                db.add(dl)
                db.flush()
                if send(r.user_id, [_dose_message(dl.id, r.medication, slot)]):
                    sent += 1
                    events.emit("dose_reminder_sent", service=SERVICE, user_id=r.user_id)
                else:
                    db.delete(dl)  # se reintenta en el próximo tick
        # 2) tomas pospuestas
        for dl in db.scalars(select(DoseLog).where(DoseLog.status == "snoozed", DoseLog.snooze_until <= now)):
            r = db.get(Reminder, dl.reminder_id)
            if r and send(dl.user_id, [_dose_message(dl.id, r.medication, dl.slot)]):
                dl.status, dl.snooze_until = "sent", None
                resent += 1
        # 3) sin respuesta
        limit = now - timedelta(hours=EXPIRE_AFTER_HOURS)
        for dl in db.scalars(select(DoseLog).where(DoseLog.status == "sent", DoseLog.sent_at < limit)):
            dl.status = "expired"
            expired += 1
            events.emit("dose_expired", service=SERVICE, user_id=dl.user_id)
        db.commit()
    return {"sent": sent, "resent": resent, "expired": expired}


# ---------- API para el dashboard ----------

@app.get("/stats", tags=["dashboard"])
def stats(days: int = 30):
    since = now_local().date() - timedelta(days=days)
    with SessionLocal() as db:
        active = db.scalar(select(func.count()).select_from(Reminder).where(Reminder.active.is_(True)))
        users = db.scalar(select(func.count(func.distinct(Reminder.user_id))).where(Reminder.active.is_(True)))
        rows = db.execute(select(DoseLog.scheduled_date, DoseLog.status, func.count())
                          .where(DoseLog.scheduled_date >= since)
                          .group_by(DoseLog.scheduled_date, DoseLog.status)).all()
    series: dict[str, dict[str, int]] = defaultdict(lambda: {"taken": 0, "skipped": 0, "expired": 0, "pending": 0})
    totals = {"taken": 0, "skipped": 0, "expired": 0, "pending": 0}
    for d, status, n in rows:
        key = status if status in ("taken", "skipped", "expired") else "pending"
        series[d.isoformat()][key] += n
        totals[key] += n
    answered = totals["taken"] + totals["skipped"] + totals["expired"]
    return {
        "active_reminders": active,
        "patients_with_reminders": users,
        "totals": totals,
        "adherence_rate": round(totals["taken"] / answered, 4) if answered else None,
        "series": [{"date": k, **v} for k, v in sorted(series.items())],
    }
