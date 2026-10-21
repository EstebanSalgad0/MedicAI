"""Orquestador de diálogo.

Recibe cada mensaje (desde el gateway de WhatsApp o el simulador web), decide
qué microservicio lo atiende y registra la telemetría de la interacción:

  1. Señales de alarma (siempre primero, sin depender de modelos).
  2. Opción tocada en un botón/lista -> se enruta por prefijo (agd:, rec:, ...).
  3. Texto libre -> NLU híbrido. Si hay un trámite en curso, el texto va a ese
     servicio salvo que el usuario pida cancelar o volver al menú.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any

import httpx
from fastapi import Depends
from pydantic import BaseModel, Field

from medicai_common import events
from medicai_common.contracts import DialogRequest, DialogResponse
from medicai_common.messages import Message
from medicai_common.messages import text as text_msg
from medicai_common.safety import EMERGENCY_TEXT, MENTAL_HEALTH_TEXT, red_flag
from medicai_common.textutil import normalize
from medicai_common.service import INTERNAL_TOKEN, create_service, require_internal, setup_logging

from . import sessions, system

SERVICE = "orchestrator"
log = setup_logging(SERVICE)
app = create_service(SERVICE, "Orquestador de diálogo: enruta mensajes a los microservicios y mide cada interacción.")

SERVICES = {
    "agendamiento": os.getenv("AGENDAMIENTO_URL", "http://ms-agendamiento:8000"),
    "recordatorios": os.getenv("RECORDATORIOS_URL", "http://ms-recordatorios:8000"),
    "orientacion": os.getenv("ORIENTACION_URL", "http://ms-orientacion:8000"),
    "derivacion": os.getenv("DERIVACION_URL", "http://ms-derivacion:8000"),
    "medicamentos": os.getenv("MEDICAMENTOS_URL", "http://ms-medicamentos:8000"),
    "resultados": os.getenv("RESULTADOS_URL", "http://ms-resultados:8000"),
    "atencion": os.getenv("ATENCION_URL", "http://ms-atencion:8000"),
}
PREFIX = {"agd": "agendamiento", "rec": "recordatorios", "ori": "orientacion", "der": "derivacion",
          "med": "medicamentos", "res": "resultados", "ate": "atencion"}
INTENT_SERVICE = {
    "agendar_cita": "agendamiento", "ver_citas": "agendamiento", "cancelar_cita": "agendamiento",
    "recordatorio_medicamento": "recordatorios", "ver_recordatorios": "recordatorios",
    "orientacion_sintomas": "orientacion", "salud_mental": "orientacion", "guia_ruta": "derivacion",
    "farmacia": "medicamentos", "ver_retiros": "medicamentos",
    "resultados_examenes": "resultados",
    "tramites_fonasa": "atencion", "modo_cuidador": "atencion", "hablar_persona": "atencion",
    "info_hospital": "atencion", "visitas": "atencion", "preparacion_examenes": "atencion",
}
START_INTENT = {"agendamiento": "agendar_cita", "recordatorios": "recordatorio_medicamento",
                "orientacion": "orientacion_sintomas", "derivacion": "guia_ruta", "medicamentos": "farmacia",
                "resultados": "resultados_examenes", "atencion": "hablar_persona"}
# En modo cuidador estos trámites se hacen a nombre del paciente a cargo.
ACTING_SERVICES = {"agendamiento", "recordatorios", "resultados", "medicamentos"}
ANALYTICS_URL = os.getenv("ANALYTICS_URL", "http://analytics:8000")
# Modo gestión: números autorizados (separados por coma). El simulador del dashboard lo
# usan funcionarios con sesión iniciada, así que también puede consultarlo.
GESTION_USERS = {u.strip() for u in os.getenv("GESTION_USERS", "").split(",") if u.strip()}
GESTION_SIMULADOR = os.getenv("GESTION_SIMULADOR", "true").lower() == "true"
GESTION_WORDS = ("ausentismo", "inasistencia", "cama", "uci", "urgencia", "pabellon", "quirofano",
                 "lista de espera", "listas de espera", "auto-resolucion", "autoresolucion", "chatbot",
                 "ocupacion", "fill-the-gap", "horas recuperadas", "satisfaccion", "indicador")
INTERRUPTS = {"cancelar", "salir", "menu", "menu principal", "volver", "inicio", "hola", "ayuda", "olvidalo"}


def is_interrupt(text: str) -> bool:
    t = normalize(text).strip(" .!¡?¿")
    return t in INTERRUPTS
NLU_URL = os.getenv("NLU_URL", "http://nlu:8000")
SURVEY_ENABLED = os.getenv("SURVEY_ENABLED", "true").lower() == "true"
SURVEY_COOLDOWN = int(os.getenv("SURVEY_COOLDOWN_HOURS", "24")) * 3600
HEADERS = {"X-Internal-Token": INTERNAL_TOKEN}
http = httpx.Client(timeout=8.0, headers=HEADERS)


class InboundMessage(BaseModel):
    user_id: str
    channel: str = "whatsapp"
    name: str | None = None
    text: str = ""
    option_id: str | None = None
    media: str | None = None  # tipo de adjunto no soportado (imagen, audio, ...)


class OutboundReply(BaseModel):
    messages: list[Message] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


def nlu_parse(text: str) -> dict:
    try:
        r = http.post(f"{NLU_URL}/parse", json={"text": text})
        r.raise_for_status()
        return r.json()
    except Exception as exc:  # noqa: BLE001
        log.error("NLU no disponible: %s", exc)
        return {"intent": "nlu_fallback", "confidence": 0.0, "entities": {}, "source": "error", "latency_ms": 0}


def call_service(service: str, req: DialogRequest) -> DialogResponse:
    r = http.post(f"{SERVICES[service]}/dialog", json=req.model_dump())
    r.raise_for_status()
    return DialogResponse(**r.json())


def is_gestion(uid: str) -> bool:
    return uid in GESTION_USERS or (GESTION_SIMULADOR and uid.startswith("web:"))


def ask_analytics(question: str) -> str:
    try:
        r = http.post(f"{ANALYTICS_URL}/ask", json={"question": question}, timeout=8)
        r.raise_for_status()
        return r.json()["answer"]
    except Exception as exc:  # noqa: BLE001
        log.error("Analítica no disponible: %s", exc)
        return "😕 No pude consultar los indicadores en este momento. Inténtalo en unos minutos."


def get_acting(uid: str) -> dict | None:
    raw = sessions.store.get(f"acting:{uid}")
    return json.loads(raw) if raw else None


# Últimas líneas de la conversación: se entregan como contexto al derivar a una persona.
TRANSCRIPT_LINES = 16


def transcript(uid: str) -> list[str]:
    return json.loads(sessions.store.get(f"transcript:{uid}") or "[]")


def remember_lines(uid: str, lines: list[str]) -> None:
    if lines:
        sessions.store.set(f"transcript:{uid}", json.dumps((transcript(uid) + lines)[-TRANSCRIPT_LINES:]), 86400)


def process(msg: InboundMessage) -> OutboundReply:
    t0 = time.perf_counter()
    uid = msg.user_id
    session = sessions.load(uid)
    out: list[Message] = []
    meta: dict[str, Any] = {"interaction_id": uuid.uuid4().hex, "channel": msg.channel,
                            "active_service_before": session.get("service")}
    nlu: dict[str, Any] = {}
    service: str | None = None
    domain_events = []
    flows: list[tuple[str, str, dict]] = []  # (evento, servicio, props)
    resolved = False
    error = None

    def abandon(reason: str):
        if session.get("service"):
            flows.append(("flow_abandoned", session["service"], {"reason": reason, "turns": session.get("turns", 0)}))

    def end_session(reason: str = "interrupted"):
        abandon(reason)
        sessions.clear(uid)

    acting = get_acting(uid)
    gestion = is_gestion(uid)
    tapped = json.loads(sessions.store.get(f"lastopts:{uid}") or "{}").get(msg.option_id or "", msg.option_id)
    remember_lines(uid, [f"Paciente: {msg.text or tapped or '(adjunto)'}"[:160]])

    def menu(greet: bool = False):
        return system.menu(msg.name, greet=greet, acting=acting, gestion=gestion)

    try:
        flag = None if msg.option_id else red_flag(msg.text)
        if msg.media and not msg.text and not msg.option_id:
            out.append(system.unsupported_media())
        elif flag:
            out.append(text_msg(MENTAL_HEALTH_TEXT if flag == "salud_mental" else EMERGENCY_TEXT))
            meta["red_flag"] = flag
            nlu = {"intent": "emergencia", "confidence": 1.0, "source": "safety", "latency_ms": 0}
            end_session("red_flag")
        elif msg.option_id and msg.option_id.startswith("sys:"):
            parts = msg.option_id.split(":")
            action = parts[1]
            if action == "survey":
                rating = int(parts[2])
                meta["survey_rating"] = rating
                # qué trámite se está evaluando (lo guardó el turno que envió la encuesta)
                ctx = json.loads(sessions.store.get(f"survey_ctx:{uid}") or "{}")
                sessions.store.delete(f"survey_ctx:{uid}")
                meta["survey_service"], meta["survey_center"] = ctx.get("service"), ctx.get("center")
                out.append(system.survey_thanks())
            elif action == "help":
                out.append(system.help_text())
            elif action == "more":
                out.append(system.more_menu(gestion))
            elif action == "gestion" and gestion:
                end_session()
                out.append(system.gestion_menu())
            elif action == "ask" and gestion:
                out.append(system.gestion_answer(ask_analytics(parts[2] if len(parts) > 2 else "")))
                meta["gestion"] = True
            else:
                end_session()
                out.append(menu())
        elif (gestion and not session.get("service") and msg.text
              and any(w in normalize(msg.text) for w in GESTION_WORDS)):
            # Analítica conversacional: "¿cómo va el ausentismo?" (solo indicadores agregados)
            out.append(system.gestion_answer(ask_analytics(msg.text)))
            meta["gestion"] = True
        else:
            start = False
            req_intent, entities = None, {}
            if msg.option_id:
                service = PREFIX.get(msg.option_id.split(":")[0])
                start = msg.option_id.endswith(":start")
                req_intent = START_INTENT.get(service) if start else None
            elif session.get("service") and not is_interrupt(msg.text):
                # Texto dentro de un trámite (un nombre, una hora, síntomas): lo interpreta el
                # propio servicio; no se consulta el NLU ni cuenta como "no entendido".
                service = session["service"]
                meta["in_flow"] = True
            else:
                nlu = nlu_parse(msg.text)
                intent, entities = nlu["intent"], nlu.get("entities", {})
                if intent in INTENT_SERVICE:
                    service, start, req_intent = INTENT_SERVICE[intent], True, intent
                else:
                    end_session(intent)
                    if intent == "saludo" or intent == "menu":
                        out.append(menu(greet=intent == "saludo"))
                    elif intent == "ayuda":
                        out.append(system.help_text())
                    elif intent == "agradecer":
                        out.append(system.thanks(msg.name))
                    elif intent == "despedida":
                        out.append(system.bye(msg.name))
                    elif intent == "cancelar":
                        out.append(system.cancelled())
                    else:
                        n = sessions.store.incr(f"fallbacks:{uid}", 600)
                        out.extend(system.fallback(n, menu()))
                        meta["fallback"] = True
                        meta["human_handoff_offered"] = n >= 3

            hops = 0
            while service and hops < 2:  # hops > 0 = un servicio pidió continuar en otro (handoff)
                hops += 1
                same = session.get("service") == service and not start
                as_patient = acting if acting and service in ACTING_SERVICES else None
                if service == "atencion":  # contexto para derivar a una persona sin repetir todo
                    entities = {**entities, "transcript": transcript(uid), "acting": acting or {}}
                resp = call_service(service, DialogRequest(
                    user_id=as_patient["id"] if as_patient else uid, channel=msg.channel,
                    name=as_patient["name"] if as_patient else msg.name, text=msg.text,
                    option_id=msg.option_id if hops == 1 else None, intent=req_intent,
                    entities=entities, state=session.get("state", {}) if same else {}, start=start))
                if resp.acting is not None:  # el servicio de atención activó o cerró el modo cuidador
                    if resp.acting:
                        sessions.store.set(f"acting:{uid}", json.dumps(resp.acting), 4 * 3600)
                    else:
                        sessions.store.delete(f"acting:{uid}")
                    acting = resp.acting or None
                if not same:
                    abandon("switched")  # el trámite anterior quedó sin completar
                    flows.append(("flow_started", service, {"via": "handoff" if hops > 1 else
                                                            ("option" if msg.option_id else "nlu")}))
                    session = {"service": service, "started_at": time.time(), "turns": 0}
                out.extend(resp.messages)
                resolved = resolved or resp.resolved
                domain_events.extend((service, e) for e in resp.events)
                meta.setdefault("services", []).append(service)
                if resp.state is None:
                    flows.append(("flow_completed", service, {
                        "resolved": resp.resolved, "turns": session.get("turns", 0) + 1,
                        "duration_s": round(time.time() - session.get("started_at", time.time()), 1)}))
                    sessions.clear(uid)
                    session = {}
                else:
                    session.update(state=resp.state, turns=session.get("turns", 0) + 1)
                    sessions.save(uid, session)
                if resp.handoff:
                    service, start = resp.handoff.service, True
                    req_intent, entities = resp.handoff.intent, resp.handoff.entities
                    session = {}
                else:
                    service = None
            if meta.get("services"):
                sessions.store.delete(f"fallbacks:{uid}")

        completed_ok = any(f[0] == "flow_completed" and f[2]["resolved"] for f in flows)
        if (SURVEY_ENABLED and completed_ok and not session.get("service")
                and not sessions.store.get(f"surveyed:{uid}")):
            sessions.store.set(f"surveyed:{uid}", "1", SURVEY_COOLDOWN)
            rated = next(f[1] for f in flows if f[0] == "flow_completed" and f[2]["resolved"])
            center = next((e.center for svc, e in domain_events if svc == rated and e.center), None)
            sessions.store.set(f"survey_ctx:{uid}", json.dumps({"service": rated, "center": center}), SURVEY_COOLDOWN)
            out.append(system.survey())
            meta["survey_sent"] = True
        if not session.get("service") and not meta.get("red_flag"):
            out = system.with_menu_button(out)  # trámite terminado: ofrecer volver al menú
    except Exception as exc:  # noqa: BLE001
        log.exception("Error procesando mensaje")
        error = type(exc).__name__
        sessions.clear(uid)
        # botón antiguo de otro trámite (ya cerrado): no es una falla técnica para el paciente
        stale = bool(msg.option_id) and PREFIX.get(msg.option_id.split(":")[0]) != meta.get("active_service_before")
        out = [system.stale_option()] if stale else [text_msg("⚠️ Tuve un problema técnico procesando tu mensaje. Inténtalo de nuevo en unos minutos. "
                        "Si es urgente llama al 131.")]

    remember_lines(uid, [f"MedicAI: {m.text.splitlines()[0].replace('*', '') if m.text else ''}"[:160] for m in out])
    # el texto de cada botón, para que el resumen muestre «🔁 Reprogramar mi hora» y no un identificador
    sessions.store.set(f"lastopts:{uid}", json.dumps({o.id: o.title for m in out for o in m.options}), 86400)
    latency = round((time.perf_counter() - t0) * 1000, 1)
    meta.update(latency_ms=latency, nlu=nlu or None)
    record(msg, meta, nlu, flows, resolved, error, domain_events)
    return OutboundReply(messages=out, meta=meta)


def record(msg, meta, nlu, flows, resolved, error, domain_events) -> None:
    services = meta.get("services") or []
    events.emit("interaction", service=services[0] if services else "orchestrator", user_id=msg.user_id,
                channel=msg.channel, props={
                    "interaction_id": meta["interaction_id"],
                    "latency_ms": meta["latency_ms"],
                    "input": "option" if msg.option_id else "media" if msg.media else "flow_text" if meta.get("in_flow") else "text",
                    "intent": nlu.get("intent"), "confidence": nlu.get("confidence"),
                    "nlu_source": nlu.get("source"), "nlu_latency_ms": nlu.get("latency_ms"),
                    "fallback": bool(meta.get("fallback")), "human_handoff_offered": bool(meta.get("human_handoff_offered")),
                    "red_flag": meta.get("red_flag"), "resolved": resolved, "survey_sent": bool(meta.get("survey_sent")), "handoff": len(services) > 1, "error": error,
                })
    if meta.get("survey_rating"):
        events.emit("survey_response", service="orchestrator", user_id=msg.user_id, channel=msg.channel,
                    center=meta.get("survey_center"),
                    props={"rating": meta["survey_rating"], "flow_service": meta.get("survey_service")})
    for ev_type, service, props in flows:
        events.emit(ev_type, service=service, user_id=msg.user_id, channel=msg.channel, props=props)
    for service, ev in domain_events:
        events.emit(ev.type, service=service, user_id=msg.user_id, channel=msg.channel, center=ev.center,
                    props=ev.props)


@app.post("/message", response_model=OutboundReply, dependencies=[Depends(require_internal)], tags=["chat"])
def post_message(msg: InboundMessage) -> OutboundReply:
    return process(msg)


class WebChatIn(BaseModel):
    session_id: str
    text: str = ""
    option_id: str | None = None
    name: str | None = "Simulador"


@app.post("/chat", response_model=OutboundReply, tags=["simulador"])
def web_chat(body: WebChatIn) -> OutboundReply:
    """Canal web del simulador del dashboard (pruebas de usabilidad sin WhatsApp)."""
    return process(InboundMessage(user_id=f"web:{body.session_id[:40]}", channel="web", name=body.name,
                                  text=body.text, option_id=body.option_id))
