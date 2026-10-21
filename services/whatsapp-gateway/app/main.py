"""Gateway de canales: WhatsApp (Meta Cloud API o 360dialog), entrada y salida, y bandeja del simulador web."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time

import httpx
from fastapi import BackgroundTasks, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel

from medicai_common import events
from medicai_common.messages import Message
from medicai_common.service import INTERNAL_TOKEN, create_service, require_internal, setup_logging

from . import providers
from .whatsapp import parse_inbound, to_payloads

SERVICE = "whatsapp-gateway"
log = setup_logging(SERVICE)
app = create_service(SERVICE, "Webhook de WhatsApp Business, envío con reintentos y bandeja del simulador web.")

VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN") or os.getenv("VERIFY_TOKEN", "")
APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "")  # firma de Meta (solo proveedor meta)
# 360dialog no firma los webhooks: al registrar la URL se le pide enviar este secreto como header.
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
WEBHOOK_SECRET_HEADER = "X-MedicAI-Webhook-Secret"
PROVIDER = providers.load()
DRY_RUN = os.getenv("WHATSAPP_DRY_RUN", "auto").lower() == "true" or not PROVIDER.configured
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8000")
# Reacción al mensaje del paciente para mostrar que el bot lo vio (vacío = sin reacción)
REACTION_EMOJI = os.getenv("WHATSAPP_REACTION_EMOJI", "👀")

if os.getenv("REDIS_URL"):
    import redis
    kv = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
else:  # desarrollo
    kv = None
    _mem: dict[str, list[str]] = {}
    _seen: set[str] = set()

if DRY_RUN:
    log.warning("WhatsApp en modo DRY_RUN (%s sin credenciales): los mensajes se registran pero no se envían",
                PROVIDER.name)
else:
    log.info("WhatsApp conectado vía %s", PROVIDER.name)


# ---------- utilidades ----------

def first_time(message_id: str) -> bool:
    """Meta reintenta webhooks; cada mensaje se procesa una sola vez."""
    if not message_id:
        return True
    if kv:
        return bool(kv.set(f"wamid:{message_id}", 1, nx=True, ex=86400))
    if message_id in _seen:
        return False
    _seen.add(message_id)
    return True


def outbox_push(user_id: str, messages: list[Message]) -> None:
    data = [json.dumps(m.model_dump(), ensure_ascii=False) for m in messages]
    if kv:
        kv.rpush(f"outbox:{user_id}", *data)
        kv.expire(f"outbox:{user_id}", 86400)
    else:
        _mem.setdefault(user_id, []).extend(data)


def wa_post(payload: dict, attempts: int = 3) -> bool:
    if DRY_RUN:
        log.info("[DRY_RUN] → %s", json.dumps(payload, ensure_ascii=False)[:500])
        return True
    delay = 0.5
    for i in range(attempts):
        try:
            r = httpx.post(PROVIDER.send_url, json=payload, timeout=10, headers=PROVIDER.headers)
            if r.status_code < 300:
                return True
            if r.status_code not in (429, 500, 502, 503, 504):
                log.error("WhatsApp rechazó el mensaje (%s): %s", r.status_code, r.text[:300])
                return False
            log.warning("WhatsApp %s, reintento %s/%s", r.status_code, i + 1, attempts)
        except httpx.HTTPError as exc:
            log.warning("Error de red con WhatsApp (%s), reintento %s/%s", exc, i + 1, attempts)
        time.sleep(delay)
        delay *= 2
    return False


def deliver(to: str, messages: list[Message]) -> tuple[int, int]:
    """Envía al canal que corresponde. Devuelve (enviados, fallidos)."""
    if to.startswith("cui:"):
        # Modo cuidador (cui:<cuidador>:<RUN del paciente>): el aviso le llega al cuidador
        to = to[4:].rsplit(":", 1)[0]
        messages = [m.model_copy(update={"text": "👪 _Modo cuidador_\n" + m.text}) for m in messages]
    if to.startswith("web:"):
        outbox_push(to, messages)
        return len(messages), 0
    ok = fail = 0
    for m in messages:
        for p in to_payloads(to, m):
            if wa_post(p):
                ok += 1
            else:
                fail += 1
    return ok, fail


# ---------- webhook de WhatsApp ----------

@app.get("/webhook", tags=["whatsapp"])
def verify(mode: str = Query(alias="hub.mode", default=""), token: str = Query(alias="hub.verify_token", default=""),
           challenge: str = Query(alias="hub.challenge", default="")):
    if mode == "subscribe" and VERIFY_TOKEN and hmac.compare_digest(token, VERIFY_TOKEN):
        return Response(content=challenge, media_type="text/plain")
    raise HTTPException(403, "Token de verificación inválido")


def acknowledge(item: dict) -> None:
    """Muestra al paciente que su mensaje llegó: doble check azul, «escribiendo…» y una reacción."""
    read = {"messaging_product": "whatsapp", "status": "read", "message_id": item["id"]}
    # el indicador de escritura dura hasta que llega la respuesta (máx. 25 s)
    if not wa_post({**read, "typing_indicator": {"type": "text"}}, attempts=1):
        wa_post(read, attempts=1)
    if REACTION_EMOJI and item.get("text") and not item.get("option_id"):  # solo a mensajes escritos
        wa_post({"messaging_product": "whatsapp", "recipient_type": "individual", "to": item["from"],
                 "type": "reaction", "reaction": {"message_id": item["id"], "emoji": REACTION_EMOJI}}, attempts=1)


def handle_inbound(item: dict, received_at: float) -> None:
    try:
        if not DRY_RUN:
            acknowledge(item)
        r = httpx.post(f"{ORCHESTRATOR_URL}/message", timeout=20, headers={"X-Internal-Token": INTERNAL_TOKEN},
                       json={"user_id": item["from"], "channel": "whatsapp", "name": item["name"],
                             "text": item["text"], "option_id": item["option_id"], "media": item["media"]})
        r.raise_for_status()
        messages = [Message(**m) for m in r.json()["messages"]]
        ok, fail = deliver(item["from"], messages)
        events.emit("delivery", service=SERVICE, user_id=item["from"], channel="whatsapp",
                    props={"end_to_end_ms": round((time.time() - received_at) * 1000, 1),
                           "sent": ok, "failed": fail, "dry_run": DRY_RUN})
    except Exception:  # noqa: BLE001
        log.exception("No se pudo procesar el mensaje %s", item.get("id"))
        deliver(item["from"], [Message(text="⚠️ Tuve un problema técnico. Inténtalo de nuevo en unos minutos. "
                                            "Si es urgente llama al 131.")])


@app.post("/webhook", tags=["whatsapp"])
async def receive(request: Request, background: BackgroundTasks):
    raw = await request.body()
    if (WEBHOOK_SECRET and PROVIDER.name == "360dialog"
            and not hmac.compare_digest(request.headers.get(WEBHOOK_SECRET_HEADER, ""), WEBHOOK_SECRET)):
        raise HTTPException(401, "Secreto de webhook inválido")
    if APP_SECRET and PROVIDER.name == "meta":
        sig = request.headers.get("X-Hub-Signature-256", "")
        expected = "sha256=" + hmac.new(APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise HTTPException(401, "Firma inválida")
    try:
        body = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(400, "JSON inválido") from None
    received_at = time.time()
    queued = 0
    for item in parse_inbound(body):
        if first_time(item["id"]):
            background.add_task(handle_inbound, item, received_at)
            queued += 1
    # Meta exige responder 200 rápido; el procesamiento sigue en segundo plano.
    return {"status": "ok", "queued": queued}


# ---------- envío interno y simulador ----------

class SendIn(BaseModel):
    to: str
    messages: list[Message]


@app.post("/internal/send", dependencies=[Depends(require_internal)], tags=["interno"])
def internal_send(body: SendIn):
    ok, fail = deliver(body.to, body.messages)
    if fail and not ok:
        raise HTTPException(502, "No se pudo entregar el mensaje")
    return {"sent": ok, "failed": fail}


@app.get("/outbox/{user_id}", tags=["simulador"])
def outbox(user_id: str):
    """Mensajes proactivos (recordatorios) pendientes para una sesión del simulador web."""
    if not user_id.startswith("web:"):
        raise HTTPException(400, "Solo disponible para el simulador")
    if kv:
        pipe = kv.pipeline()
        pipe.lrange(f"outbox:{user_id}", 0, -1)
        pipe.delete(f"outbox:{user_id}")
        items = pipe.execute()[0]
    else:
        items = _mem.pop(user_id, [])
    return {"messages": [json.loads(i) for i in items]}


@app.get("/status", tags=["infra"])
def status():
    return {"provider": PROVIDER.name, "dry_run": DRY_RUN,
            "meta_signature_check": bool(APP_SECRET) and PROVIDER.name == "meta",
            "shared_secret_check": bool(WEBHOOK_SECRET)}
