"""Detección de señales de alarma. Se evalúa antes que cualquier otra lógica
(orquestador y orientación) y no depende del NLU ni de un LLM.

Usa patrones por signo clínico (no frases exactas) para tolerar redacciones
distintas. Debe revisarse con el equipo clínico y medirse con
`scripts/evaluar_nlu.py` (intención `emergencia` del conjunto reservado).
"""
from __future__ import annotations

import re

from .textutil import normalize

URGENCIA_PATRONES = [
    r"\b(ayuda urgente|emergencia|accidente|ambulancia|samu)\b",
    # vía aérea / respiración
    r"\bno (puedo|puede|podia|logra|alcanza a) respirar\b", r"\bno respira\b", r"\b(me|se) (ahogo|ahoga|asfixia)\b",
    # conciencia
    r"\bno (despierta|reacciona|responde)\b", r"\binconsciente\b", r"\bperdi(o|da)? (el|la) (conocimiento|conciencia)\b",
    r"\bse desmayo\b", r"\bconvulsi",
    # dolor torácico con signos de alarma
    r"\bpecho\b.*\b(brazo|mandibula|apret|opresi|fuerte|intens|aplast)", r"\b(fuerte|intens)\w* .*\bpecho\b",
    # signos de accidente cerebrovascular
    r"\b(cara|boca) chueca\b", r"\bno (puede|puedo) hablar\b", r"\bse (me|le) durmio (la mitad|medio)\b", r"\bparalisis\b",
    # otros
    r"\bsangra(do)? (mucho|abundante)|\bhemorragia\b|\bsangrando mucho\b",
    r"\b(envenen|intoxic)", r"\bquemadura grave\b",
]
RIESGO_VITAL_SALUD_MENTAL = [
    r"suicid", r"quitarme la vida", r"\bmatarme\b", r"no quiero (vivir|seguir viviendo)", r"hacerme dano", r"autolesion",
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
    "🚨 *Esto puede ser una emergencia*\n\n"
    "📞 Llama ahora al *131 (SAMU)* o acude al SAPU/SAR o urgencia más cercana.\n"
    "• Bomberos: 132 · Carabineros: 133\n\n"
    "No esperes la respuesta de este chat. Si estás con alguien, pídele ayuda. 💙"
)
MENTAL_HEALTH_TEXT = (
    "💙 Lamento que estés pasando por esto. No estás solo/a y hay personas preparadas para ayudarte ahora.\n\n"
    "📞 *Línea de Prevención del Suicidio: \\*4141* (gratuita, 24 horas)\n"
    "📞 *Salud Responde: 600 360 7777*\n"
    "🚑 Si estás en peligro inmediato, llama al *131* o acude a la urgencia más cercana.\n\n"
    "Si puedes, cuéntale a alguien de confianza cómo te sientes."
)
