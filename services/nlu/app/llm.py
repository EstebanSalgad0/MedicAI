"""Clasificación de respaldo con un modelo de lenguaje (LLM).

Se invoca solo cuando Rasa no alcanza el umbral de confianza. El LLM elige una
etiqueta de una lista cerrada; nunca genera respuestas al paciente ni decide
orientación clínica.

Proveedores (LLM_PROVIDER):
  anthropic  API de Anthropic (LLM_API_KEY, LLM_MODEL)
  openai     cualquier API compatible con OpenAI (LLM_BASE_URL), p. ej. Ollama local:
             permite mantener los datos dentro de la infraestructura del Servicio de Salud.
  none       desactivado
"""
from __future__ import annotations

import json
import logging
import os
import re

import httpx

from .intents import INTENTS

PROVIDER = os.getenv("LLM_PROVIDER", "none").lower()
API_KEY = os.getenv("LLM_API_KEY", "")
MODEL = os.getenv("LLM_MODEL", "claude-haiku-5-5")
BASE_URL = os.getenv("LLM_BASE_URL", "http://ollama:11434/v1")
TIMEOUT = float(os.getenv("LLM_TIMEOUT_SECONDS", "4"))
log = logging.getLogger("nlu.llm")

SYSTEM = (
    "Eres el clasificador de intenciones de MedicAI, asistente de Atención Primaria de Salud en Chile. "
    "Recibes un mensaje de un paciente (español de Chile, puede tener faltas de ortografía) y debes "
    "elegir UNA intención de la lista. Responde solo JSON: "
    '{"intent": "<etiqueta>", "confidence": <0..1>, "medicamento": "<nombre o null>"}. '
    "Si nada calza, usa \"nlu_fallback\".\n\nIntenciones:\n"
    + "\n".join(f"- {k}: {v}" for k, v in INTENTS.items())
)

_RUT = re.compile(r"\b\d{1,2}\.?\d{3}\.?\d{3}-?[\dkK]\b")
_PHONE = re.compile(r"\+?56\s?9\s?\d{4}\s?\d{4}|\b9\d{8}\b")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def redact(text: str) -> str:
    """Quita RUT, teléfonos y correos antes de enviar texto a un proveedor externo."""
    return _EMAIL.sub("[correo]", _PHONE.sub("[telefono]", _RUT.sub("[rut]", text)))


def enabled() -> bool:
    return PROVIDER in ("anthropic", "openai") and (PROVIDER == "openai" or bool(API_KEY))


def classify(text: str) -> dict | None:
    if not enabled():
        return None
    msg = redact(text)[:500]
    try:
        if PROVIDER == "anthropic":
            r = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": MODEL, "max_tokens": 80, "system": SYSTEM,
                      "messages": [{"role": "user", "content": msg}]},
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            raw = r.json()["content"][0]["text"]
        else:
            headers = {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}
            r = httpx.post(
                f"{BASE_URL}/chat/completions", headers=headers, timeout=TIMEOUT,
                json={"model": MODEL, "temperature": 0, "max_tokens": 80,
                      "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": msg}]},
            )
            r.raise_for_status()
            raw = r.json()["choices"][0]["message"]["content"]
        data = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
        intent = data.get("intent")
        if intent not in INTENTS:
            intent = "nlu_fallback"
        ents = {"medicamento": data["medicamento"]} if data.get("medicamento") else {}
        return {"intent": intent, "confidence": float(data.get("confidence", 0.7)), "entities": ents}
    except Exception as exc:  # noqa: BLE001
        log.warning("LLM no disponible o respuesta inválida: %s", exc)
        return None
