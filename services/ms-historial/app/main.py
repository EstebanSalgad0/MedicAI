"""Módulo 1 — Dashboard clínico: perfil sintético del paciente desde una o varias bases de la red.

Permisos (antes de entregar cualquier dato clínico):
  1. El usuario ingresó con ClaveÚnica y tiene un rol clínico.
  2. Tiene relación asistencial con el paciente: registros en un establecimiento donde trabaja
     o una derivación activa hacia él. Sin relación solo se permite el acceso excepcional por
     urgencia, que queda marcado en la auditoría.
Cada acceso, permitido o denegado, queda auditado.
"""
from __future__ import annotations

import json
import os
import time
from typing import Literal

import httpx
from fastapi import Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from medicai_common import auth, events, rut
from medicai_common.auth import Funcionario
from medicai_common.service import INTERNAL_TOKEN, create_service, require_internal, setup_logging
from medicai_common.textutil import now_local, today_local

from . import clinica, dictado, fuentes, ia, perfil
from .models import Acceso, Ficha, SessionLocal, init_db

SERVICE = "historial"
log = setup_logging(SERVICE)
app = create_service(SERVICE, "Ficha clínica multi-establecimiento con citas de fuente, alertas, apoyo diagnóstico "
                              "y ficha por dictado (Módulo 1).", on_startup=init_db)

DERIVACION_URL = os.getenv("DERIVACION_URL", "http://ms-derivacion:8000")
ASR_URL = os.getenv("ASR_URL", "").rstrip("/")
ASR_MODEL = os.getenv("ASR_MODEL", "whisper-1")
Motivo = Literal["atencion", "interconsulta", "continuidad", "urgencia"]


def run_valido(run: str) -> str:
    limpio = rut.valid(run)
    if not limpio:
        raise HTTPException(422, "RUN inválido")
    return limpio


def seleccion(establecimientos: str | None) -> list[str]:
    ids = [e for e in (establecimientos or "").split(",") if e]
    if not ids:
        return list(fuentes.NOMBRE_EST)
    malos = [e for e in ids if e not in fuentes.NOMBRE_EST]
    if malos:
        raise HTTPException(422, f"Establecimiento desconocido: {', '.join(malos)}")
    return ids


def auditar(prof: Funcionario, run: str, ests: list[str], accion: str, motivo: str, resultado: str,
            detalle: str | None = None) -> None:
    with SessionLocal() as db:
        db.add(Acceso(profesional_run=prof.run, profesional_nombre=prof.nombre, rol=prof.rol, paciente_run=run,
                      establecimientos=ests, accion=accion, motivo=motivo, resultado=resultado, detalle=detalle))
        db.commit()
    events.emit("clinical_access", service=SERVICE, props={"accion": accion, "motivo": motivo,
                                                           "resultado": resultado, "fuentes": len(ests)})


def derivacion_activa(run: str, destinos: list[str]) -> bool:
    try:
        r = httpx.get(f"{DERIVACION_URL}/internal/derivaciones/activas", params={"run": run,
                      "destinos": ",".join(destinos)}, headers={"X-Internal-Token": INTERNAL_TOKEN}, timeout=2)
        r.raise_for_status()
        return bool(r.json().get("activas"))
    except Exception as exc:  # noqa: BLE001
        log.warning("No se pudo consultar derivaciones: %s", exc)
        return False


def verificar(prof: Funcionario, run: str, ests: list[str], accion: str, motivo: str) -> dict[str, fuentes.Resultado]:
    """Comprueba la relación asistencial. Devuelve los resultados ya obtenidos de las bases
    propias del profesional para no consultarlas dos veces."""
    propios = [e for e in prof.establecimientos if e in fuentes.NOMBRE_EST]
    previos = {r.establecimiento_id: r for r in fuentes.consultar(run, propios)}
    if any(r.estado == "ok" for r in previos.values()):
        auditar(prof, run, ests, accion, motivo, "permitido", "relación asistencial: registros en su establecimiento")
    elif propios and derivacion_activa(run, propios):
        auditar(prof, run, ests, accion, motivo, "permitido", "relación asistencial: derivación activa")
    elif motivo == "urgencia":
        auditar(prof, run, ests, accion, motivo, "excepcional_urgencia", "acceso sin relación previa por urgencia")
    else:
        auditar(prof, run, ests, accion, motivo, "denegado", "sin relación asistencial registrada")
        raise HTTPException(403, "No tiene relación asistencial registrada con este paciente en sus "
                                 "establecimientos. Si es una urgencia, use el motivo «urgencia»: el acceso "
                                 "quedará registrado como excepcional.")
    return previos


def consultar(run: str, ests: list[str], previos: dict[str, fuentes.Resultado]):
    """Resultados de la selección, reutilizando los ya obtenidos (en orden de llegada)."""
    for e in ests:
        if e in previos:
            yield previos[e]
    yield from fuentes.consultar(run, [e for e in ests if e not in previos])


# ---------- perfil ----------

@app.get("/establecimientos", tags=["dashboard"])
def establecimientos(prof: Funcionario = Depends(auth.funcionario)):
    return [{"id": k, "nombre": n, "tipo": fuentes.TIPO_EST[k], "nivel": fuentes.NIVEL_EST[k],
             "propio": k in prof.establecimientos} for k, n in fuentes.NOMBRE_EST.items()]


@app.get("/pacientes/{run}/perfil", tags=["dashboard"])
def perfil_paciente(run: str, establecimientos: str | None = None, motivo: Motivo = "atencion",
                    prof: Funcionario = Depends(auth.requiere_clinico)):
    run, ests = run_valido(run), seleccion(establecimientos)
    t0 = time.perf_counter()
    previos = verificar(prof, run, ests, "perfil", motivo)
    p = perfil.construir(run, list(consultar(run, ests, previos)), today_local())
    return {**perfil.publico(p), "generado_ms": round((time.perf_counter() - t0) * 1000)}


@app.get("/pacientes/{run}/perfil/stream", tags=["dashboard"])
def perfil_stream(run: str, establecimientos: str | None = None, motivo: Motivo = "atencion",
                  prof: Funcionario = Depends(auth.requiere_clinico)):
    """Igual que /perfil, pero informa el progreso: una línea JSON por cada base que responde
    y al final el perfil completo (NDJSON)."""
    run, ests = run_valido(run), seleccion(establecimientos)
    t0 = time.perf_counter()
    previos = verificar(prof, run, ests, "perfil", motivo)

    def lineas():
        yield json.dumps({"evento": "inicio", "fuentes": ests}) + "\n"
        resultados = []
        for r in consultar(run, ests, previos):
            resultados.append(r)
            yield json.dumps({"evento": "fuente", **r.resumen()}) + "\n"
        p = perfil.construir(run, resultados, today_local())
        yield json.dumps({"evento": "perfil", "perfil": perfil.publico(p),
                          "generado_ms": round((time.perf_counter() - t0) * 1000)}, default=str) + "\n"

    return StreamingResponse(lineas(), media_type="application/x-ndjson",
                             headers={"X-Accel-Buffering": "no", "Cache-Control": "no-store"})


class ApoyoIn(BaseModel):
    cuadro: str = Field(min_length=3, max_length=2000)
    establecimientos: list[str] = Field(default_factory=list)
    motivo: Motivo = "atencion"


@app.post("/pacientes/{run}/apoyo", tags=["dashboard"])
def apoyo_diagnostico(run: str, body: ApoyoIn, prof: Funcionario = Depends(auth.requiere_clinico)):
    run, ests = run_valido(run), seleccion(",".join(body.establecimientos))
    previos = verificar(prof, run, ests, "apoyo", body.motivo)
    p = perfil.construir(run, list(consultar(run, ests, previos)), today_local())
    regs = list(p["registros"].values())
    hipotesis = clinica.apoyo(body.cuadro, regs) + ia.hipotesis(body.cuadro, p["registros"])
    return {
        "hipotesis": hipotesis,
        "sin_resultados": None if hipotesis else ("No se encontraron hipótesis respaldadas por las reglas "
                                                  "configuradas y los registros disponibles para este cuadro."),
        "modelo_local": ia.disponible(),
        "aviso": "Hipótesis y exámenes sugeridos para validación médica. No constituyen diagnóstico ni indicación.",
    }


# ---------- ficha por dictado ----------

class DictadoIn(BaseModel):
    texto: str = Field(min_length=1, max_length=20000)


@app.post("/fichas/estructurar", tags=["dictado"])
def estructurar(body: DictadoIn, _: Funcionario = Depends(auth.requiere_clinico)):
    return dictado.estructurar(body.texto)


@app.post("/fichas/transcribir", tags=["dictado"])
def transcribir(audio: UploadFile = File(...), _: Funcionario = Depends(auth.requiere_clinico)):
    """Transcribe el audio con un servicio de reconocimiento de voz LOCAL (ASR_URL, API compatible
    con /audio/transcriptions, p. ej. faster-whisper). Sin ASR local no se transcribe: el audio
    de una consulta no sale del establecimiento."""
    if not ASR_URL:
        raise HTTPException(503, "La transcripción local no está configurada (ASR_URL). Escriba o pegue el texto.")
    data = audio.file.read(25 * 1024 * 1024 + 1)
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(413, "El audio supera 25 MB")
    try:
        r = httpx.post(f"{ASR_URL}/audio/transcriptions", timeout=120,
                       files={"file": (audio.filename or "dictado.webm", data, audio.content_type or "audio/webm")},
                       data={"model": ASR_MODEL, "language": "es"})
        r.raise_for_status()
        return {"texto": r.json().get("text", "").strip()}
    except Exception as exc:  # noqa: BLE001
        log.error("ASR no disponible: %s", exc)
        raise HTTPException(502, "El servicio de transcripción local no respondió.") from None


class Seccion(BaseModel):
    id: Literal[tuple(dictado.SECCIONES)]  # type: ignore[valid-type]
    texto: str = Field(default="", max_length=10000)


class FichaIn(BaseModel):
    paciente_run: str
    establecimiento_id: str
    transcripcion: str = Field(default="", max_length=20000)
    secciones: list[Seccion]
    origen: str = "reglas"


def _ficha(f: Ficha) -> dict:
    return {"id": f.id, "paciente_run_mask": rut.mask(f.paciente_run), "establecimiento_id": f.establecimiento_id,
            "establecimiento": fuentes.NOMBRE_EST.get(f.establecimiento_id), "profesional": f.profesional_nombre,
            "secciones": [{**s, "titulo": dictado.SECCIONES.get(s["id"], s["id"])} for s in f.secciones],
            "transcripcion": f.transcripcion, "origen": f.origen, "estado": f.estado,
            "created_at": f.created_at, "firmada_at": f.firmada_at}


@app.post("/fichas", tags=["dictado"])
def crear_ficha(body: FichaIn, prof: Funcionario = Depends(auth.requiere_clinico)):
    run = run_valido(body.paciente_run)
    if body.establecimiento_id not in prof.establecimientos:
        raise HTTPException(403, "Solo puede registrar fichas en un establecimiento donde trabaja.")
    with SessionLocal() as db:
        f = Ficha(paciente_run=run, establecimiento_id=body.establecimiento_id, profesional_run=prof.run or prof.sub,
                  profesional_nombre=prof.firma, transcripcion=body.transcripcion, origen=body.origen[:80],
                  secciones=[s.model_dump() for s in body.secciones])
        db.add(f)
        db.commit()
        out = _ficha(f)
    auditar(prof, run, [body.establecimiento_id], "ficha", "atencion", "permitido", f"borrador #{out['id']}")
    return out


def _propia(db, ficha_id: int, prof: Funcionario) -> Ficha:
    f = db.get(Ficha, ficha_id)
    if not f or f.profesional_run != (prof.run or prof.sub):
        raise HTTPException(404, "Ficha no encontrada")
    if f.estado == "firmada":
        raise HTTPException(409, "La ficha ya está firmada y no puede modificarse.")
    return f


@app.put("/fichas/{ficha_id}", tags=["dictado"])
def editar_ficha(ficha_id: int, body: FichaIn, prof: Funcionario = Depends(auth.requiere_clinico)):
    with SessionLocal() as db:
        f = _propia(db, ficha_id, prof)
        f.secciones = [s.model_dump() for s in body.secciones]
        db.commit()
        return _ficha(f)


@app.post("/fichas/{ficha_id}/firmar", tags=["dictado"])
def firmar_ficha(ficha_id: int, prof: Funcionario = Depends(auth.requiere_clinico)):
    with SessionLocal() as db:
        f = _propia(db, ficha_id, prof)
        if not any((s.get("texto") or "").strip() for s in f.secciones):
            raise HTTPException(422, "La ficha está vacía.")
        f.estado, f.firmada_at = "firmada", now_local().replace(tzinfo=None)
        db.commit()
        out = _ficha(f)
    events.emit("clinical_note_signed", service=SERVICE, props={"origen": out["origen"]})
    return out


@app.get("/pacientes/{run}/fichas", tags=["dictado"])
def fichas_paciente(run: str, prof: Funcionario = Depends(auth.requiere_clinico)):
    run = run_valido(run)
    with SessionLocal() as db:
        q = select(Ficha).where(Ficha.paciente_run == run,
                                (Ficha.estado == "firmada") | (Ficha.profesional_run == (prof.run or prof.sub)))
        return [_ficha(f) for f in db.scalars(q.order_by(Ficha.created_at.desc()).limit(50))]


# ---------- auditoría y configuración ----------

@app.get("/auditoria", tags=["dashboard"])
def auditoria(run: str | None = None, limit: int = Query(100, le=500), prof: Funcionario = Depends(auth.funcionario)):
    if prof.rol != "admin":
        raise HTTPException(403, "Solo administración puede revisar la auditoría de accesos.")
    q = select(Acceso).order_by(Acceso.id.desc()).limit(limit)
    if run:
        q = q.where(Acceso.paciente_run == run_valido(run))
    with SessionLocal() as db:
        return [{"ts": a.ts, "profesional": a.profesional_nombre, "rol": a.rol, "paciente": rut.mask(a.paciente_run),
                 "accion": a.accion, "motivo": a.motivo, "resultado": a.resultado, "detalle": a.detalle,
                 "establecimientos": a.establecimientos} for a in db.scalars(q)]


@app.get("/config", tags=["dashboard"])
def config(_: Funcionario = Depends(auth.funcionario)):
    return {"modelo_local": ia.disponible(), "transcripcion_local": bool(ASR_URL),
            "fuentes": os.getenv("FUENTES_MODE", "demo"), "timeout_s": fuentes.TIMEOUT_S}


# ---------- interno: controles que el chat puede sugerir al paciente ----------

@app.get("/internal/controles-sugeridos/{run}", dependencies=[Depends(require_internal)], tags=["interno"])
def controles_sugeridos(run: str):
    limpio = rut.valid(run)
    if not limpio:
        return {"controles": []}
    aps = [e for e in fuentes.NOMBRE_EST if fuentes.TIPO_EST[e] == "CESFAM"]
    return {"controles": perfil.controles_sugeridos(list(fuentes.consultar(limpio, aps, timeout=2)), today_local())}
