"""Clasificación de respaldo con un modelo de lenguaje (LLM).

Se invoca solo cuando Rasa no alcanza el umbral de confianza. El LLM elige una
etiqueta de una lista cerrada; nunca genera respuestas al paciente ni decide
orientación clínica.

El proveedor lo define la política común (`medicai_common.llm`): por defecto un modelo
local (Ollama). Un proveedor externo solo se usa si LLM_ALLOW_EXTERNAL=true, y aun así
el texto viaja sin RUT, teléfonos ni correos.
"""
from __future__ import annotations

import json
import logging
import re

from medicai_common import llm as common_llm
from medicai_common import prompts

from .intents import INTENTS

log = logging.getLogger("nlu.llm")

SYSTEM = prompts.para_modulo(2, (
    "Actúas solo como clasificador de intenciones del chatbot de pacientes. No respondes al paciente. "
    "Recibes un mensaje (español de Chile, puede tener faltas de ortografía) y eliges UNA intención de la "
    'lista. Responde solo JSON: {"intent": "<etiqueta>", "confidence": <0..1>, "medicamento": "<nombre o null>"}. '
    "Si nada calza, usa \"nlu_fallback\".\n\nIntenciones:\n"
    + "\n".join(f"- {k}: {v}" for k, v in INTENTS.items())
))

_RUT = re.compile(r"\b\d{1,2}\.?\d{3}\.?\d{3}-?[\dkK]\b")
_PHONE = re.compile(r"\+?56\s?9\s?\d{4}\s?\d{4}|\b9\d{8}\b")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def redact(text: str) -> str:
    """Quita RUT, teléfonos y correos antes de enviar texto a un modelo."""
    return _EMAIL.sub("[correo]", _PHONE.sub("[telefono]", _RUT.sub("[rut]", text)))


def enabled() -> bool:
    return common_llm.enabled()


def classify(text: str) -> dict | None:
    raw = common_llm.complete(SYSTEM, redact(text)[:500], max_tokens=80)
    if not raw:
        return None
    try:
        data = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
    except ValueError as exc:
        log.warning("Respuesta del LLM no es JSON: %s", exc)
        return None
    intent = data.get("intent")
    if intent not in INTENTS:
        intent = "nlu_fallback"
    ents = {"medicamento": data["medicamento"]} if data.get("medicamento") else {}
    return {"intent": intent, "confidence": float(data.get("confidence", 0.7)), "entities": ents}
