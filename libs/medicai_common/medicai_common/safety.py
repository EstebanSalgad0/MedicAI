"""Detección de señales de alarma. Se evalúa antes que cualquier otra lógica
(orquestador y orientación) y no depende del NLU ni de un LLM.

Usa patrones por signo clínico (no frases exactas) para tolerar redacciones
distintas. Debe revisarse con el equipo clínico y medirse con
`scripts/evaluar_nlu.py` (intención `emergencia` del conjunto reservado).
"""
from __future__ import annotations

import re

from . import hospital
from .textutil import normalize

URGENCIA_PATRONES = [
    r"\b(ayuda urgente|emergencia|ambulancia|samu)\b",
    # dolor u opresión en el pecho, infarto
    r"\b(dolor|duele|opresion|apret\w*|presion)\b.{0,25}\b(pecho|torax|toracico)\b",
    r"\b(pecho|torax)\b.{0,25}\b(dolor|duele|opresion|apret)", r"\btoracico\b", r"\binfarto\b",
    # vía aérea / respiración
    r"\bno (puedo|puede|podia|logra|alcanza a) respirar\b", r"\bno respira\b", r"\b(me|se) (ahogo|ahoga|asfixia)\b",
    r"\bahogo\b", r"\bme falta (el )?aire\b",
    # conciencia
    r"\bno (despierta|reacciona|responde)\b", r"\binconsciente\b",
    r"\bperdi(o|da)? (el|la) (conocimiento|conciencia)\b", r"\bperdida de (conocimiento|conciencia)\b",
    r"\b(se|me) desmay", r"\bdesmayo\b", r"\bconvulsi",
    # signos de accidente cerebrovascular
    r"\b(cara|boca) chueca\b", r"\bno (puede|puedo) hablar\b", r"\bse (me|le) durmio (la mitad|medio)\b",
    r"\bparalisis\b",
    # traumatismos y sangrado
    r"\bsangra(do)? (mucho|abundante)|\bhemorragia\b|\bsangrando mucho\b", r"\bherida profunda\b",
    r"\baccidente (grave|de transito|de auto|en moto)\b", r"\batropell",
    r"\bquemadura (grave|extensa|grande)\b", r"\bgolpe (fuerte )?en la cabeza\b", r"\bse golpeo la cabeza\b",
    # intoxicaciones
    r"\b(envenen|intoxic)",
    # fiebre con rigidez de nuca; lactante deshidratado
    r"\bfiebre\b.{0,40}\b(rigidez|cuello rigido|nuca rigida)",
    r"\b(rigidez|cuello rigido|nuca rigida)\b.{0,40}\bfiebre\b",
    r"\b(bebe|guagua|lactante)\b.{0,40}\b(deshidrat|no moja (el )?panal|no orina|ojos hundidos)",
]
RIESGO_VITAL_SALUD_MENTAL = [
    r"suicid", r"quitarme la vida", r"\bmatarme\b", r"no quiero (vivir|seguir viviendo)", r"hacerme dano",
    r"autolesion", r"\bme quiero morir\b", r"\bquiero morirme\b",
]
_U = [re.compile(p) for p in URGENCIA_PATRONES]
_M = [re.compile(p) for p in RIESGO_VITAL_SALUD_MENTAL]


def red_flag(text: str) -> str | None:
    t = normalize(text)
    if any(p.search(t) for p in _M):
        return "salud_mental"
    if t.strip() == "131" or any(p.search(t) for p in _U):
        return "urgencia"
    return None


EMERGENCY_TEXT = (
    "🚨 *Esto puede ser una emergencia.*\n\n"
    "Llama ahora al *SAMU 131* o acude de inmediato a *Urgencias del "
    f"{hospital.NOMBRE}* ({hospital.DIRECCION}, atención 24/7) o a la urgencia más cercana.\n\n"
    "Si puedes, pide a alguien que te acompañe. No esperes respuesta del chat."
)
MENTAL_HEALTH_TEXT = (
    "Lamento mucho que estés pasando por esto. No estás solo/a y hay personas preparadas para ayudarte ahora.\n\n"
    "📞 Llama al *\\*4141* (SaludableMente, prevención del suicidio): gratuito, 24/7.\n"
    "🚑 Si estás en peligro inmediato, llama al *SAMU 131* o acude a Urgencias del "
    f"{hospital.NOMBRE} ({hospital.DIRECCION}) o a la urgencia más cercana.\n\n"
    "Si puedes, cuéntale ahora a alguien de confianza cómo te sientes y pídele que te acompañe."
)
