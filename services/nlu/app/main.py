"""NLU híbrido: Rasa NLU -> LLM (si Rasa duda) -> palabras clave (modo degradado).

Cada respuesta informa qué motor resolvió (`source`) y su latencia: con eso el
servicio de analítica calcula la contribución de cada capa a la precisión y a
la tasa de fallback, que es evidencia experimental para el avance de TRL.
"""
from __future__ import annotations

import os
import time

import httpx
from fastapi import Depends
from pydantic import BaseModel, Field

from medicai_common import llm as common_llm
from medicai_common.safety import red_flag
from medicai_common.service import create_service, require_internal, setup_logging

from . import llm
from .intents import INTENTS, keyword_intent

SERVICE = "nlu"
log = setup_logging(SERVICE)
app = create_service(SERVICE, "Interpretación de mensajes: Rasa NLU con respaldo de LLM y reglas.")

RASA_URL = os.getenv("RASA_URL", "http://nlu-rasa:5005")
RASA_THRESHOLD = float(os.getenv("RASA_CONFIDENCE_THRESHOLD", "0.70"))


class ParseIn(BaseModel):
    text: str
    use_llm: bool = True


class ParseOut(BaseModel):
    intent: str
    confidence: float
    entities: dict = Field(default_factory=dict)
    source: str  # safety | rasa | llm | rules | fallback
    latency_ms: float
    rasa_intent: str | None = None
    rasa_confidence: float | None = None


def rasa_parse(text: str) -> dict | None:
    try:
        r = httpx.post(f"{RASA_URL}/model/parse", json={"text": text}, timeout=3)
        r.raise_for_status()
        return r.json()
    except Exception as exc:  # noqa: BLE001
        log.warning("Rasa no disponible: %s", exc)
        return None


def _entities(rasa: dict | None) -> dict:
    out: dict = {}
    for e in (rasa or {}).get("entities", []):
        out.setdefault(e["entity"], e.get("value"))
    return out


def parse(text: str, use_llm: bool = True) -> ParseOut:
    t0 = time.perf_counter()

    def done(intent, conf, source, ents=None, rasa=None):
        ri = (rasa or {}).get("intent") or {}
        return ParseOut(intent=intent, confidence=round(conf, 4), entities=ents or {}, source=source,
                        latency_ms=round((time.perf_counter() - t0) * 1000, 1),
                        rasa_intent=ri.get("name"), rasa_confidence=ri.get("confidence"))

    if red_flag(text):
        return done("emergencia", 1.0, "safety")

    rasa = rasa_parse(text)
    ents = _entities(rasa)
    if rasa:
        ri = rasa.get("intent") or {}
        if ri.get("name") in INTENTS and (ri.get("confidence") or 0) >= RASA_THRESHOLD:
            return done(ri["name"], ri["confidence"], "rasa", ents, rasa)

    if use_llm:
        res = llm.classify(text)
        if res and res["intent"] != "nlu_fallback":
            return done(res["intent"], res["confidence"], "llm", {**ents, **res["entities"]}, rasa)

    kw = keyword_intent(text)
    if kw:
        return done(kw, 0.5, "rules", ents, rasa)
    return done("nlu_fallback", 0.0, "fallback", ents, rasa)


@app.post("/parse", response_model=ParseOut, dependencies=[Depends(require_internal)], tags=["nlu"])
def post_parse(body: ParseIn) -> ParseOut:
    return parse(body.text, body.use_llm)


@app.get("/intents", tags=["nlu"])
def intents():
    return {"intents": INTENTS, "rasa_threshold": RASA_THRESHOLD,
            "llm": {"provider": os.getenv("LLM_PROVIDER", "none"), "local": common_llm.is_local(),
                    "model": os.getenv("LLM_MODEL") if llm.enabled() else None}}
