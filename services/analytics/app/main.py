"""Servicio de analítica: recibe eventos de todos los servicios, calcula KPIs y
autentica a los funcionarios que usan el dashboard."""
from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx
import jwt
from fastapi import Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from medicai_common.service import create_service, require_internal, setup_logging
from medicai_common.textutil import TZ

from . import ask, hospital, kpis
from .models import Event, SessionLocal, init_db

SERVICE = "analytics"
log = setup_logging(SERVICE)
app = create_service(SERVICE, "Telemetría seudonimizada, indicadores del proyecto y autenticación del dashboard.",
                     on_startup=init_db)

SALT = os.getenv("ANALYTICS_SALT", "cambiar-en-produccion")
JWT_SECRET = os.getenv("JWT_SECRET", "cambiar-en-produccion")
JWT_HOURS = int(os.getenv("JWT_HOURS", "8"))
USERS = {os.getenv("DASHBOARD_USER", "admin"): os.getenv("DASHBOARD_PASSWORD", "medicai")}
# Cuentas adicionales opcionales, formato "usuario:clave,usuario2:clave2"
for _pair in os.getenv("DASHBOARD_EXTRA_USERS", "").split(","):
    _user, _sep, _pwd = _pair.strip().partition(":")
    if _user and _sep and _pwd:
        USERS.setdefault(_user, _pwd)


def pseudonym(user_id: str | None) -> str | None:
    """Identificador estable pero no reversible (Ley 21.719: minimización y seudonimización)."""
    if not user_id:
        return None
    return hashlib.sha256(f"{SALT}:{user_id}".encode()).hexdigest()[:16]


# ---------- ingesta ----------

class EventIn(BaseModel):
    type: str
    service: str
    user_id: str | None = None
    channel: str | None = None
    center: str | None = None
    props: dict[str, Any] = Field(default_factory=dict)


class EventsIn(BaseModel):
    events: list[EventIn]


@app.post("/internal/events", dependencies=[Depends(require_internal)], tags=["ingesta"])
def ingest(body: EventsIn):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with SessionLocal() as db:
        for e in body.events:
            channel = e.channel or ("web" if (e.user_id or "").startswith("web:") else
                                    "whatsapp" if e.user_id else None)
            db.add(Event(ts=now, type=e.type[:40], service=e.service[:30], user_hash=pseudonym(e.user_id),
                         channel=channel, center=e.center, props=e.props))
        db.commit()
    return {"stored": len(body.events)}


# ---------- autenticación del dashboard ----------

class LoginIn(BaseModel):
    username: str
    password: str


@app.post("/auth/login", tags=["auth"])
def login(body: LoginIn):
    expected = USERS.get(body.username)
    if not expected or not hmac.compare_digest(expected, body.password):
        raise HTTPException(401, "Usuario o contraseña incorrectos")
    exp = datetime.now(timezone.utc) + timedelta(hours=JWT_HOURS)
    token = jwt.encode({"sub": body.username, "exp": exp}, JWT_SECRET, algorithm="HS256")
    return {"token": token, "expires_at": exp.isoformat(), "user": body.username}


def current_user(authorization: str = Header(default="")) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Falta token")
    try:
        return jwt.decode(authorization[7:], JWT_SECRET, algorithms=["HS256"])["sub"]
    except jwt.PyJWTError:
        raise HTTPException(401, "Token inválido o expirado") from None


@app.get("/auth/verify", tags=["auth"])
def verify(user: str = Depends(current_user)):
    """Usado por el gateway nginx (auth_request) para proteger todas las rutas /api/."""
    return {"user": user}


# ---------- consultas ----------

def load(days: int, date_from: date | None, date_to: date | None, center: str | None, channel: str | None):
    if date_from is None:
        date_from = datetime.now(TZ).date() - timedelta(days=days - 1)
    start = datetime.combine(date_from, datetime.min.time(), TZ).astimezone(timezone.utc).replace(tzinfo=None)
    q = select(Event).where(Event.ts >= start)
    if date_to:
        end = datetime.combine(date_to + timedelta(days=1), datetime.min.time(), TZ)
        q = q.where(Event.ts < end.astimezone(timezone.utc).replace(tzinfo=None))
    if center:
        q = q.where(Event.center == center)
    if channel:
        q = q.where(Event.channel == channel)
    with SessionLocal() as db:
        return list(db.scalars(q.order_by(Event.ts)))


class Filters:
    def __init__(self, days: int = Query(30, ge=1, le=730), date_from: date | None = None,
                 date_to: date | None = None, center: str | None = None, channel: str | None = None):
        self.args = (days, date_from, date_to, center, channel)


@app.get("/kpis", tags=["dashboard"])
def get_kpis(f: Filters = Depends()):
    return kpis.summary(load(*f.args))


@app.get("/timeseries", tags=["dashboard"])
def get_timeseries(f: Filters = Depends()):
    return kpis.timeseries(load(*f.args))


@app.get("/services", tags=["dashboard"])
def get_services(f: Filters = Depends()):
    return kpis.per_service(load(*f.args))


@app.get("/intents", tags=["dashboard"])
def get_intents(f: Filters = Depends()):
    return kpis.intents(load(*f.args))


@app.get("/satisfaction", tags=["dashboard"])
def get_satisfaction(f: Filters = Depends(), limit: int = Query(50, ge=1, le=500)):
    return kpis.satisfaction(load(*f.args), limit)


AGENDAMIENTO_URL = os.getenv("AGENDAMIENTO_URL", "http://ms-agendamiento:8000")


def _agenda() -> tuple[list[dict] | None, dict | None]:
    """Inasistencia por día y de hoy desde el microservicio de agendamiento (tolerante a fallas)."""
    try:
        daily = httpx.get(f"{AGENDAMIENTO_URL}/stats/daily", params={"days": 28}, timeout=4).json()
        today = httpx.get(f"{AGENDAMIENTO_URL}/stats", timeout=4).json().get("today")
        return daily, today
    except Exception as exc:  # noqa: BLE001
        log.warning("Agendamiento no disponible para el panel: %s", exc)
        return None, None


@app.get("/hospital", tags=["gestión"])
def get_hospital():
    """Panel de gestión del hospital: operación (simulada en el prototipo), agenda y alertas."""
    now = datetime.now(TZ).replace(tzinfo=None)
    snap = hospital.snapshot(now)
    daily, today = _agenda()
    gap_today = (daily or [{}])[-1].get("gap_filled", 0) if daily else 0
    return {**snap, "agenda": {"daily": (daily or [])[-14:], "today": today},
            "alertas": hospital.alerts(snap, (daily or [])[-14:], gap_today)}


@app.get("/chatbot/panel", tags=["gestión"])
def get_chatbot_panel(days: int = Query(14, ge=1, le=365)):
    return kpis.chatbot_panel(load(days, None, None, None, None), days)


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=300)


@app.post("/ask", tags=["gestión"])
def post_ask(body: AskIn):
    """Analítica conversacional: pregunta en lenguaje natural → respuesta con datos agregados."""
    now = datetime.now(TZ).replace(tzinfo=None)
    daily, today = _agenda()
    bot = kpis.chatbot_panel(load(14, None, None, None, None), 14)
    return ask.answer(body.question, hospital.snapshot(now), daily, today, bot)


@app.get("/events", tags=["dashboard"])
def recent(limit: int = Query(50, le=500), type: str | None = None):
    q = select(Event).order_by(Event.id.desc()).limit(limit)
    if type:
        q = q.where(Event.type == type)
    with SessionLocal() as db:
        return [{"id": e.id, "ts": e.ts.replace(tzinfo=timezone.utc).isoformat(), "type": e.type, "service": e.service,
                 "user": e.user_hash, "channel": e.channel, "center": e.center, "props": e.props}
                for e in db.scalars(q)]


@app.get("/export.csv", tags=["dashboard"])
def export(f: Filters = Depends()):
    """Exporta eventos seudonimizados para el análisis estadístico del equipo de investigación."""
    rows = load(*f.args)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "timestamp_utc", "tipo", "servicio", "usuario_seudonimo", "canal", "centro", "propiedades_json"])
    for e in rows:
        w.writerow([e.id, e.ts.isoformat(), e.type, e.service, e.user_hash, e.channel, e.center,
                    json.dumps(e.props, ensure_ascii=False)])
    buf.seek(0)
    name = f"medicai_eventos_{datetime.now(TZ):%Y%m%d}.csv"
    return StreamingResponse(iter(["﻿" + buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})
