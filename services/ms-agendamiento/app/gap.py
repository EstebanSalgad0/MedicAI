"""Fill-the-gap: cuando se libera una hora, se ofrece al siguiente paciente compatible
de la lista de espera.

El orden respeta la priorización (GES primero) y la antigüedad en la lista, no la
rapidez en responder. Cada oferta queda registrada en `gap_offers` y vence a los
GAP_OFFER_MINUTES; si el paciente no la toma, pasa al siguiente.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

from sqlalchemy import select

from medicai_common import events
from medicai_common.messages import buttons
from medicai_common.notify import send
from medicai_common.textutil import now_local

from .catalog import CENTRO_NOMBRE, PRESTACION_NOMBRE
from .models import Appointment, GapOffer, SessionLocal, Waitlist

SERVICE = "agendamiento"
GAP_OFFER_MINUTES = int(os.getenv("GAP_OFFER_MINUTES", "30"))
DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


def fmt_slot(dt: datetime) -> str:
    return f"{DIAS[dt.weekday()]} {dt:%d-%m} · {dt:%H:%M}"


def offer_gap(center_id: str, prestacion: str, slot: datetime) -> bool:
    """Ofrece el cupo `slot` al primer paciente compatible. Devuelve True si se ofreció."""
    now = now_local().replace(tzinfo=None)
    if slot < now + timedelta(hours=1):
        return False
    with SessionLocal() as db:
        if db.scalar(select(Appointment.id).where(Appointment.center_id == center_id, Appointment.prestacion == prestacion,
                                                  Appointment.slot_at == slot, Appointment.status == "confirmed")):
            return False  # alguien ya lo tomó
        if db.scalar(select(GapOffer.id).where(GapOffer.slot_at == slot, GapOffer.center_id == center_id,
                                               GapOffer.prestacion == prestacion, GapOffer.status == "offered")):
            return False  # ya hay una oferta vigente por este cupo
        candidates = db.scalars(
            select(Waitlist).where(Waitlist.center_id == center_id, Waitlist.prestacion == prestacion,
                                   Waitlist.status == "waiting")
            .order_by(Waitlist.priority.desc(), Waitlist.created_at, Waitlist.id))
        for wl in candidates:
            if db.scalar(select(GapOffer.id).where(GapOffer.waitlist_id == wl.id, GapOffer.slot_at == slot)):
                continue  # ya se le ofreció este cupo
            if db.scalar(select(GapOffer.id).where(GapOffer.waitlist_id == wl.id, GapOffer.status == "offered")):
                continue  # está decidiendo otra oferta
            if wl.appointment_id:
                current = db.get(Appointment, wl.appointment_id)
                if not current or current.status != "confirmed":
                    wl.status = "cancelled"
                    continue
                if current.slot_at <= slot:
                    continue  # el cupo no es mejor que la hora que ya tiene
            offer = GapOffer(waitlist_id=wl.id, slot_at=slot, center_id=center_id, prestacion=prestacion,
                             offered_at=now)
            db.add(offer)
            db.flush()
            antes = ""
            if wl.appointment_id:
                antes = f"\nEs antes que tu hora actual ({fmt_slot(db.get(Appointment, wl.appointment_id).slot_at)})."
            msg = buttons(
                f"⚡ *¡Se liberó una hora!*\n\n👩‍⚕️ {PRESTACION_NOMBRE.get(prestacion, prestacion)}\n"
                f"🏥 {CENTRO_NOMBRE.get(center_id, center_id)}\n📅 {fmt_slot(slot)}{antes}\n\n"
                f"¿La quieres? La guardo para ti por {GAP_OFFER_MINUTES} minutos.",
                [(f"agd:gap:{offer.id}:yes", "✅ La quiero"), (f"agd:gap:{offer.id}:no", "No, gracias")],
                "Lista de espera • MedicAI")
            if send(wl.user_id, [msg]):
                db.commit()
                events.emit("gap_offered", service=SERVICE, user_id=wl.user_id, center=center_id,
                            props={"prestacion": prestacion, "priority": wl.priority})
                return True
            offer.status = "expired"  # no se pudo avisar: se prueba con el siguiente
        db.commit()
    return False


def expire_offers() -> int:
    """Vence las ofertas sin respuesta y pasa el cupo al siguiente de la lista."""
    limit = now_local().replace(tzinfo=None) - timedelta(minutes=GAP_OFFER_MINUTES)
    with SessionLocal() as db:
        stale = list(db.scalars(select(GapOffer).where(GapOffer.status == "offered", GapOffer.offered_at < limit)))
        for o in stale:
            o.status = "expired"
        db.commit()
    for o in stale:
        offer_gap(o.center_id, o.prestacion, o.slot_at)
    return len(stale)
