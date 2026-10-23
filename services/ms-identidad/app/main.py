"""Identidad con ClaveÚnica para profesionales y pacientes.

- Profesionales: ingresan al dashboard con ClaveÚnica. Si su RUN está habilitado, reciben un
  token con su rol y sus establecimientos; con eso cada servicio decide qué pueden ver.
- Pacientes: el chat nunca pide RUN, claves ni datos de pago. Cuando un trámite necesita
  identidad (resultados, derivaciones, modo cuidador), el chat envía un enlace de un solo uso;
  el paciente ingresa con ClaveÚnica y su número de WhatsApp queda vinculado a su RUN.
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal

import httpx
from fastapi import Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from medicai_common import auth, events, rut
from medicai_common.messages import buttons
from medicai_common.notify import send
from medicai_common.service import INTERNAL_TOKEN, create_service, require_internal, setup_logging

from . import claveunica, paginas
from .models import Profesional, SessionLocal, Solicitud, Vinculo, init_db

SERVICE = "identidad"
log = setup_logging(SERVICE)
ENLACE_MINUTOS = int(os.getenv("CLAVEUNICA_ENLACE_MINUTOS", "10"))
ATENCION_URL = os.getenv("ATENCION_URL", "http://ms-atencion:8000")
FOOTER = "Identidad • MedicAI"
RELACIONES = [("hijo", "Hijo/a"), ("pareja", "Cónyuge o pareja"), ("padre", "Madre o padre"),
              ("hermano", "Hermano/a"), ("otro", "Otro familiar o cuidador")]

# Identidades de prueba (solo CLAVEUNICA_MODE=demo). Los RUN se calculan con su dígito verificador.
_DEMO_PROS = [
    (15111111, "Dra. Ana Rojas Vidal", "medico", ["las_americas", "hrt"]),
    (16222222, "Dr. Pedro Muñoz Lagos", "medico", ["hrt"]),
    (17333333, "Carla Díaz Soto", "enfermeria", ["julio_contardo"]),
    (18444444, "Marta Fuentes Pérez", "matrona", ["curico_centro"]),
    (19555555, "Luis Pino Araya", "some", ["las_americas", "hrt"]),
]
DEMO_PACIENTES = [("12345678-5", "Juan Pérez Soto", "Paciente de prueba (caso con varios establecimientos)"),
                  ("11111111-1", "María González Rojas", "Paciente de prueba")]


def _run(n: int) -> str:
    return f"{n}-{rut.dv(n)}"


def seed() -> None:
    """Carga profesionales de prueba (modo demo) y los definidos en PROFESIONALES:
    `RUN|rol|est1,est2|Nombre;RUN|rol|est|Nombre`."""
    filas = []
    if claveunica.mode() == "demo" and os.getenv("PROFESIONALES_DEMO", "true").lower() == "true":
        filas += [(_run(n), nombre, rol, ests) for n, nombre, rol, ests in _DEMO_PROS]
    for item in os.getenv("PROFESIONALES", "").split(";"):
        partes = [p.strip() for p in item.split("|")]
        if len(partes) == 4 and rut.valid(partes[0]) and partes[1] in auth.ROL_NOMBRE:
            filas.append((rut.valid(partes[0]), partes[3], partes[1], [e for e in partes[2].split(",") if e]))
    with SessionLocal() as db:
        for run, nombre, rol, ests in filas:
            if not db.get(Profesional, run):
                db.add(Profesional(run=run, nombre=nombre, rol=rol, establecimientos=ests))
        db.commit()


def startup() -> None:
    init_db()
    seed()
    if claveunica.mode() == "demo":
        log.warning("ClaveÚnica en MODO DEMO: cualquiera puede ingresar con cualquier RUN. Solo para pruebas con "
                    "datos simulados; para pacientes reales usa CLAVEUNICA_MODE=produccion.")


app = create_service(SERVICE, "Ingreso con ClaveÚnica de profesionales y pacientes; vínculo WhatsApp ↔ RUN "
                              "sin pedir datos de identidad por el chat.", on_startup=startup)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def html(res: tuple[str, int]) -> HTMLResponse:
    return HTMLResponse(res[0], status_code=res[1])


def nueva_solicitud(proposito: str, user_id: str | None = None, destino: str | None = None) -> str:
    token = secrets.token_urlsafe(24)
    with SessionLocal() as db:
        db.add(Solicitud(token=token, proposito=proposito, user_id=user_id, destino=destino,
                         expires_at=utcnow() + timedelta(minutes=ENLACE_MINUTOS)))
        db.commit()
    return token


def solicitud_vigente(db, token: str) -> Solicitud | None:
    s = db.get(Solicitud, token)
    if not s or s.used_at or s.expires_at < utcnow():
        return None
    return s


# ---------- API interna (servicios del chat) ----------

class SolicitudIn(BaseModel):
    user_id: str = Field(min_length=1, max_length=120)
    proposito: Literal["resultados", "cuidador", "derivacion", "agenda"]


@app.post("/internal/solicitudes", dependencies=[Depends(require_internal)], tags=["interno"])
def crear_solicitud(body: SolicitudIn):
    token = nueva_solicitud(body.proposito, user_id=body.user_id)
    return {"url": f"{claveunica.public_base()}/id/vincular/{token}", "minutos": ENLACE_MINUTOS}


@app.get("/internal/vinculos/{user_id:path}", dependencies=[Depends(require_internal)], tags=["interno"])
def obtener_vinculo(user_id: str):
    with SessionLocal() as db:
        v = db.get(Vinculo, user_id)
    if not v:
        raise HTTPException(404, "Sin identidad verificada")
    horas = (utcnow() - v.verified_at).total_seconds() / 3600
    return {"run": v.run, "nombre": v.nombre, "verified_at": v.verified_at.isoformat() + "Z",
            "horas_desde_verificacion": round(horas, 2)}


@app.get("/internal/vinculos", dependencies=[Depends(require_internal)], tags=["interno"])
def usuarios_de_run(run: str):
    limpio = rut.valid(run)
    with SessionLocal() as db:
        ids = list(db.scalars(select(Vinculo.user_id).where(Vinculo.run == limpio))) if limpio else []
    return {"user_ids": ids}


# ---------- ingreso con ClaveÚnica (páginas públicas bajo /id/) ----------

@app.get("/id/login", tags=["claveunica"])
def login_profesional(next: str = "/"):
    destino = next if next.startswith("/") and not next.startswith("//") else "/"
    return RedirectResponse(claveunica.authorize_url(nueva_solicitud("profesional", destino=destino)), 303)


@app.get("/id/vincular/{token}", tags=["claveunica"])
def vincular(token: str):
    with SessionLocal() as db:
        s = solicitud_vigente(db, token)
    if not s or s.proposito == "profesional":
        return html(paginas.mensaje("Enlace vencido", "Este enlace ya se usó o venció. Vuelve a WhatsApp y pide "
                                    "uno nuevo: dura solo unos minutos para proteger tu información.", 410))
    return RedirectResponse(claveunica.authorize_url(token), 303)


@app.get("/id/demo", tags=["claveunica"])
def demo_form(state: str):
    if claveunica.mode() != "demo":
        raise HTTPException(404)
    with SessionLocal() as db:
        s = solicitud_vigente(db, state)
        if not s:
            return html(paginas.mensaje("Enlace vencido", "Vuelve a iniciar el ingreso.", 410))
        if s.proposito == "profesional":
            sugeridos = [(p.run, p.nombre, f"{auth.ROL_NOMBRE.get(p.rol, p.rol)} · {', '.join(p.establecimientos)}")
                         for p in db.scalars(select(Profesional).where(Profesional.activo.is_(True)))]
        else:
            sugeridos = DEMO_PACIENTES
    return html(paginas.demo(state, sugeridos))


@app.post("/id/demo", tags=["claveunica"])
def demo_submit(state: str = Form(...), run: str = Form(...), nombre: str = Form(...)):
    if claveunica.mode() != "demo":
        raise HTTPException(404)
    limpio = rut.valid(run)
    if not limpio:
        return html(paginas.mensaje("RUN inválido", "Revisa el dígito verificador e inténtalo de nuevo.", 400))
    code = claveunica.demo_code(limpio, " ".join(nombre.split())[:160])
    return RedirectResponse(f"/id/callback?code={code}&state={state}", 303)


def avisar(user_id: str, proposito: str, nombre: str | None) -> None:
    hola = f", {nombre.split()[0]}" if nombre else ""
    siguiente = {"resultados": [("res:start", "📋 Ver mis exámenes")],
                 "derivacion": [("der:estado", "📍 Mis derivaciones")],
                 "agenda": [("agd:start", "📅 Agendar una hora")]}.get(proposito, [("sys:menu", "🏠 Menú principal")])
    send(user_id, [buttons(f"✅ *Identidad verificada con ClaveÚnica*\n\nGracias{hola}. Ya puedes continuar "
                           "tu trámite por aquí.", siguiente, FOOTER)])


@app.get("/id/callback", tags=["claveunica"])
def callback(state: str, code: str | None = None, error: str | None = None):
    with SessionLocal() as db:
        s = solicitud_vigente(db, state)
        if not s:
            return html(paginas.mensaje("Enlace vencido", "El ingreso tardó demasiado o el enlace ya se usó. "
                                        "Inténtalo de nuevo.", 410))
        if error or not code:
            return html(paginas.mensaje("Ingreso cancelado", "No se completó el ingreso con ClaveÚnica.", 400))
        try:
            ident = claveunica.exchange(code, state)
        except claveunica.ClaveUnicaError as exc:
            log.warning("Fallo de ClaveÚnica: %s", exc)
            return html(paginas.mensaje("ClaveÚnica no disponible", "No pudimos verificar tu identidad. "
                                        "Inténtalo en unos minutos.", 502))
        run, nombre = ident["run"], ident.get("nombre")

        if s.proposito == "profesional":
            s.used_at = utcnow()
            p = db.get(Profesional, run)
            db.commit()
            if not p or not p.activo:
                events.emit("login_rejected", service=SERVICE, props={"motivo": "run_no_habilitado"})
                return html(paginas.mensaje("Acceso no habilitado", "Tu RUN no está registrado como funcionario de "
                                            "la red. Pide el alta al administrador del establecimiento.", 403))
            token, _ = auth.emitir(auth.Funcionario(sub=run, nombre=p.nombre, rol=p.rol, run=run,
                                                    establecimientos=list(p.establecimientos or []),
                                                    metodo="claveunica"))
            events.emit("login", service=SERVICE, props={"metodo": "claveunica", "rol": p.rol})
            return RedirectResponse(f"{s.destino or '/'}#token={token}", 303)

        v = db.get(Vinculo, s.user_id)
        if v:
            v.run, v.nombre, v.verified_at = run, nombre, utcnow()
        else:
            db.add(Vinculo(user_id=s.user_id, run=run, nombre=nombre, verified_at=utcnow()))
        if s.proposito == "cuidador":  # paso 2: datos de la persona a cargo, en la web y no en el chat
            s.run, s.nombre = run, nombre
            s.expires_at = utcnow() + timedelta(minutes=15)
            db.commit()
            return html(paginas.cuidador(state, nombre or "", RELACIONES))
        s.used_at = utcnow()
        user_id, proposito = s.user_id, s.proposito
        db.commit()
    events.emit("identity_verified", service=SERVICE, user_id=user_id, props={"proposito": proposito})
    avisar(user_id, proposito, nombre)
    return html(paginas.mensaje("Identidad verificada", "Listo. Vuelve a WhatsApp: ya te enviamos la opción para "
                                "continuar."))


@app.post("/id/cuidador", tags=["claveunica"])
def registrar_cuidador(token: str = Form(...), nombre: str = Form(...), run: str = Form(...),
                       relacion: str = Form(...), declaro: str = Form("")):
    with SessionLocal() as db:
        s = solicitud_vigente(db, token)
        if not s or s.proposito != "cuidador" or not s.run:
            return html(paginas.mensaje("Enlace vencido", "Vuelve a WhatsApp y pide un enlace nuevo.", 410))
        limpio = rut.valid(run)
        error = ("El RUN no es válido: revisa el dígito verificador." if not limpio else
                 "El RUN de la persona a cargo debe ser distinto al tuyo." if limpio == s.run else
                 "Debes declarar que la persona te autorizó." if declaro != "si" else
                 "Elige una relación." if relacion not in dict(RELACIONES) else "")
        if error:
            return html(paginas.cuidador(token, s.nombre or "", RELACIONES, error))
        payload = {"caregiver_id": s.user_id, "caregiver_name": s.nombre or "Cuidador/a", "caregiver_run": s.run,
                   "patient_name": " ".join(nombre.split())[:120], "patient_run": limpio,
                   "relationship": dict(RELACIONES)[relacion]}
        try:
            r = httpx.post(f"{ATENCION_URL}/internal/caregivers", json=payload,
                           headers={"X-Internal-Token": INTERNAL_TOKEN}, timeout=8)
            r.raise_for_status()
            cid = r.json()["id"]
        except Exception as exc:  # noqa: BLE001
            log.error("No se pudo registrar al cuidador: %s", exc)
            return html(paginas.mensaje("No pudimos registrar", "Inténtalo de nuevo en unos minutos.", 502))
        s.used_at = utcnow()
        user_id = s.user_id
        db.commit()
    send(user_id, [buttons(f"✅ Quedaste registrado/a como cuidador/a de *{payload['patient_name']}*.\n\n"
                           "Esa persona puede revocar la autorización cuando quiera en Admisión.",
                           [(f"ate:cui:act:{cid}", "👤 Gestionar ahora")], FOOTER)])
    return html(paginas.mensaje("Registro listo", "Vuelve a WhatsApp para gestionar sus trámites."))


# ---------- administración de profesionales (dashboard) ----------

def requiere_admin(f: auth.Funcionario = Depends(auth.funcionario)) -> auth.Funcionario:
    if f.rol != "admin":
        raise HTTPException(403, "Solo administración puede gestionar profesionales.")
    return f


def _prof(p: Profesional) -> dict:
    return {"run": p.run, "run_mask": rut.mask(p.run), "nombre": p.nombre, "rol": p.rol,
            "rol_nombre": auth.ROL_NOMBRE.get(p.rol, p.rol), "establecimientos": p.establecimientos or [],
            "activo": p.activo}


@app.get("/profesionales", tags=["dashboard"])
def listar_profesionales(_: auth.Funcionario = Depends(requiere_admin)):
    with SessionLocal() as db:
        return [_prof(p) for p in db.scalars(select(Profesional).order_by(Profesional.nombre))]


class ProfesionalIn(BaseModel):
    run: str
    nombre: str = Field(min_length=3, max_length=120)
    rol: Literal[tuple(auth.ROL_NOMBRE)]  # type: ignore[valid-type]
    establecimientos: list[str] = Field(default_factory=list)
    activo: bool = True


@app.put("/profesionales", tags=["dashboard"])
def guardar_profesional(body: ProfesionalIn, _: auth.Funcionario = Depends(requiere_admin)):
    limpio = rut.valid(body.run)
    if not limpio:
        raise HTTPException(422, "RUN inválido")
    with SessionLocal() as db:
        p = db.get(Profesional, limpio) or Profesional(run=limpio)
        p.nombre, p.rol, p.establecimientos, p.activo = body.nombre, body.rol, body.establecimientos, body.activo
        db.add(p)
        db.commit()
        return _prof(p)


@app.get("/id/config", tags=["claveunica"])
def config():
    """Para el login del dashboard: indica si ClaveÚnica corre en modo de prueba."""
    return {"modo": claveunica.mode()}
