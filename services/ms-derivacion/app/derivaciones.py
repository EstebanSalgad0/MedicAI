"""Derivaciones con seguimiento (Módulo 3): asignación intra y extra red, con trazabilidad
hasta la atención de destino. Toda derivación queda registrada con fecha, origen, destino y
responsable, y cada cambio de estado agrega un evento al historial."""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from medicai_common import auth, events, identidad, rut
from medicai_common.auth import Funcionario
from medicai_common.centros import CENTRO_NOMBRE
from medicai_common.messages import buttons
from medicai_common.notify import send
from medicai_common.service import require_internal
from medicai_common.textutil import now_local

from .models import Derivacion, DerivacionEvento, SessionLocal

SERVICE = "derivacion"
router = APIRouter()
FOOTER = "Derivaciones • MedicAI"
# Institutos de especialidad de alcance nacional (fuera de la red regional)
EXTRA_RED = {"inst_cancer": "Instituto Nacional del Cáncer", "inst_torax": "Instituto Nacional del Tórax",
             "inst_neurocirugia": "Instituto de Neurocirugía Dr. Alfonso Asenjo"}
DESTINOS = {**CENTRO_NOMBRE, **EXTRA_RED}
TRANSICIONES = {"enviada": {"agendada", "caducada"}, "agendada": {"agendada", "atendida", "caducada"}}
ESTADO_PACIENTE = {
    "enviada": "📨 Recibida en el establecimiento de destino. Aún sin hora: te contactarán.",
    "agendada": "📅 Con hora asignada",
    "atendida": "✅ Atendida",
    "caducada": "⌛ Venció. Acércate al SOME de tu CESFAM para revisarla.",
}
CADUCA_DIAS = int(os.getenv("DERIVACION_CADUCA_DIAS", "180"))
GRACIA_DIAS = int(os.getenv("DERIVACION_GRACIA_DIAS", "30"))


def ahora() -> datetime:
    return now_local().replace(tzinfo=None)


def _out(d: Derivacion, eventos: list[DerivacionEvento] | None = None) -> dict:
    out = {"id": d.id, "folio": f"DER-{d.id:06d}", "paciente_run_mask": rut.mask(d.paciente_run),
           "paciente_nombre": d.paciente_nombre, "origen_id": d.origen_id,
           "origen": DESTINOS.get(d.origen_id, d.origen_id), "destino_id": d.destino_id,
           "destino": DESTINOS.get(d.destino_id, d.destino_id), "red": d.red, "especialidad": d.especialidad,
           "prioridad": d.prioridad, "ges": d.ges, "motivo": d.motivo, "responsable": d.responsable,
           "estado": d.estado, "fecha_cita": d.fecha_cita, "created_at": d.created_at, "updated_at": d.updated_at,
           "dias_abierta": (ahora() - d.created_at).days if d.created_at else 0}
    if eventos is not None:
        out["eventos"] = [{"estado": e.estado, "responsable": e.responsable, "nota": e.nota, "at": e.at}
                          for e in eventos]
    return out


def _evento(db, d: Derivacion, estado: str, responsable: str, nota: str | None = None) -> None:
    db.add(DerivacionEvento(derivacion_id=d.id, estado=estado, responsable=responsable, nota=nota, at=ahora()))


def _avisar_paciente(d: Derivacion) -> None:
    """Si el paciente vinculó su WhatsApp con ClaveÚnica, le avisa los cambios relevantes."""
    if d.estado not in ("agendada", "caducada"):
        return
    cuando = f"\n📅 {d.fecha_cita:%d-%m-%Y %H:%M}" if d.estado == "agendada" and d.fecha_cita else ""
    texto = (f"📋 *Tu derivación a {d.especialidad}*\n🏥 {DESTINOS.get(d.destino_id, d.destino_id)}{cuando}\n\n"
             f"{ESTADO_PACIENTE[d.estado]}")
    for uid in identidad.usuarios_de_run(d.paciente_run):
        if send(uid, [buttons(texto, [("der:estado", "📍 Mis derivaciones")], FOOTER)]):
            events.emit("referral_patient_notified", service=SERVICE, user_id=uid, props={"estado": d.estado})


# ---------- API del dashboard ----------

@router.get("/destinos", tags=["derivaciones"])
def destinos(_: Funcionario = Depends(auth.requiere_agenda)):
    return {"intra": [{"id": k, "nombre": v} for k, v in CENTRO_NOMBRE.items()],
            "extra": [{"id": k, "nombre": v} for k, v in EXTRA_RED.items()]}


class DerivacionIn(BaseModel):
    paciente_run: str
    paciente_nombre: str | None = Field(default=None, max_length=160)
    origen_id: str
    destino_id: str
    especialidad: str = Field(min_length=2, max_length=80)
    prioridad: Literal["normal", "preferente", "urgente"] = "normal"
    ges: bool = False
    motivo: str = Field(min_length=3, max_length=500)


@router.post("/derivaciones", tags=["derivaciones"])
def crear(body: DerivacionIn, f: Funcionario = Depends(auth.requiere_agenda)):
    run = rut.valid(body.paciente_run)
    if not run:
        raise HTTPException(422, "RUN inválido")
    if body.origen_id not in CENTRO_NOMBRE or body.destino_id not in DESTINOS:
        raise HTTPException(422, "Origen o destino desconocido")
    if body.origen_id == body.destino_id:
        raise HTTPException(422, "El destino debe ser distinto del origen")
    if f.rol != "admin" and body.origen_id not in f.establecimientos:
        raise HTTPException(403, "Solo puede derivar desde un establecimiento donde trabaja.")
    with SessionLocal() as db:
        d = Derivacion(paciente_run=run, paciente_nombre=body.paciente_nombre, origen_id=body.origen_id,
                       destino_id=body.destino_id, red="intra" if body.destino_id in CENTRO_NOMBRE else "extra",
                       especialidad=body.especialidad, prioridad=body.prioridad, ges=body.ges, motivo=body.motivo,
                       responsable=f.firma, created_at=ahora(), updated_at=ahora())
        db.add(d)
        db.flush()
        _evento(db, d, "enviada", f.firma, "Derivación emitida")
        db.commit()
        out = _out(d, [])
    events.emit("referral_sent", service=SERVICE, center=body.origen_id,
                props={"destino": body.destino_id, "red": out["red"], "prioridad": body.prioridad, "ges": body.ges})
    return out


@router.get("/derivaciones", tags=["derivaciones"])
def listar(estado: str | None = None, origen_id: str | None = None, destino_id: str | None = None,
           run: str | None = None, limit: int = 200, _: Funcionario = Depends(auth.requiere_agenda)):
    q = select(Derivacion).order_by(Derivacion.created_at.desc()).limit(min(limit, 1000))
    if estado:
        q = q.where(Derivacion.estado == estado)
    if origen_id:
        q = q.where(Derivacion.origen_id == origen_id)
    if destino_id:
        q = q.where(Derivacion.destino_id == destino_id)
    if run:
        q = q.where(Derivacion.paciente_run == (rut.valid(run) or ""))
    with SessionLocal() as db:
        items = list(db.scalars(q))
        evs: dict[int, list] = {}
        if items:
            for e in db.scalars(select(DerivacionEvento).where(DerivacionEvento.derivacion_id.in_([d.id for d in items]))
                                .order_by(DerivacionEvento.at, DerivacionEvento.id)):
                evs.setdefault(e.derivacion_id, []).append(e)
        counts = dict(db.execute(select(Derivacion.estado, func.count()).group_by(Derivacion.estado)).all())
        return {"items": [_out(d, evs.get(d.id, [])) for d in items], "counts": counts}


class EstadoIn(BaseModel):
    estado: Literal["agendada", "atendida", "caducada"]
    nota: str | None = Field(default=None, max_length=500)
    fecha_cita: datetime | None = None


@router.patch("/derivaciones/{der_id}", tags=["derivaciones"])
def cambiar_estado(der_id: int, body: EstadoIn, f: Funcionario = Depends(auth.requiere_agenda)):
    with SessionLocal() as db:
        d = db.get(Derivacion, der_id)
        if not d:
            raise HTTPException(404, "Derivación no encontrada")
        if f.rol != "admin" and not ({d.origen_id, d.destino_id} & set(f.establecimientos)):
            raise HTTPException(403, "La derivación no es de su establecimiento.")
        if body.estado not in TRANSICIONES.get(d.estado, set()):
            raise HTTPException(409, f"No se puede pasar de «{d.estado}» a «{body.estado}».")
        if body.estado == "agendada" and not body.fecha_cita:
            raise HTTPException(422, "Indique la fecha de la cita.")
        if body.estado == "agendada":
            d.fecha_cita = body.fecha_cita.replace(tzinfo=None)
        d.estado, d.updated_at = body.estado, ahora()
        nota = body.nota or (f"Cita: {d.fecha_cita:%d-%m-%Y %H:%M}" if body.estado == "agendada" else None)
        _evento(db, d, body.estado, f.firma, nota)
        db.commit()
        evs = list(db.scalars(select(DerivacionEvento).where(DerivacionEvento.derivacion_id == d.id)
                              .order_by(DerivacionEvento.at, DerivacionEvento.id)))
        out = _out(d, evs)
        _avisar_paciente(d)
    events.emit(f"referral_{body.estado}", service=SERVICE, center=d.destino_id,
                props={"dias": out["dias_abierta"], "red": d.red, "prioridad": d.prioridad})
    return out


# ---------- interno y tareas ----------

@router.get("/internal/derivaciones/activas", dependencies=[Depends(require_internal)], tags=["interno"])
def activas(run: str, destinos: str = ""):
    """Para ms-historial: ¿hay una derivación activa de este paciente hacia esos establecimientos?
    (cuenta como relación asistencial para acceder a la ficha)."""
    ids = [x for x in destinos.split(",") if x]
    with SessionLocal() as db:
        n = db.scalar(select(func.count()).select_from(Derivacion).where(
            Derivacion.paciente_run == (rut.valid(run) or ""), Derivacion.estado.in_(["enviada", "agendada"]),
            Derivacion.destino_id.in_(ids))) if ids else 0
    return {"activas": n}


def de_paciente(run: str) -> list[dict]:
    with SessionLocal() as db:
        return [_out(d) for d in db.scalars(select(Derivacion).where(Derivacion.paciente_run == run)
                                            .order_by(Derivacion.created_at.desc()).limit(8))]


def caducar_vencidas() -> int:
    """Caducidad por plazo: enviada sin agendar en DERIVACION_CADUCA_DIAS, o agendada sin atención
    registrada DERIVACION_GRACIA_DIAS después de la cita."""
    now = ahora()
    n = 0
    with SessionLocal() as db:
        vencidas = list(db.scalars(select(Derivacion).where(
            ((Derivacion.estado == "enviada") & (Derivacion.created_at < now - timedelta(days=CADUCA_DIAS)))
            | ((Derivacion.estado == "agendada") & (Derivacion.fecha_cita < now - timedelta(days=GRACIA_DIAS))))))
        for d in vencidas:
            motivo = (f"Sin agendar en {CADUCA_DIAS} días" if d.estado == "enviada"
                      else f"Sin atención registrada {GRACIA_DIAS} días después de la cita")
            d.estado, d.updated_at = "caducada", now
            _evento(db, d, "caducada", "Sistema (plazo vencido)", motivo)
            n += 1
        db.commit()
        for d in vencidas:
            _avisar_paciente(d)
    return n
