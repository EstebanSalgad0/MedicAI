"""Ficha por dictado: ordena la transcripción de la consulta en las secciones del registro
clínico (anamnesis, examen físico, diagnóstico, indicaciones) para revisión y firma.

Regla central: solo reorganiza lo que el profesional dijo. No agrega, no resume con
palabras nuevas y no completa secciones vacías: si algo no se dictó, lo informa.
"""
from __future__ import annotations

import json
import re

from medicai_common import llm, prompts
from medicai_common.textutil import normalize

SECCIONES = {
    "anamnesis": "Anamnesis",
    "examen_fisico": "Examen físico",
    "diagnostico": "Diagnóstico (según lo dictado por el profesional)",
    "indicaciones": "Indicaciones",
}
# encabezados explícitos («examen físico:») y frases que suelen abrir cada sección
ENCABEZADOS = {
    "anamnesis": ("anamnesis", "motivo de consulta", "consulta por", "historia actual"),
    "examen_fisico": ("examen fisico", "al examen", "examen segmentario", "signos vitales"),
    "diagnostico": ("diagnostico", "impresion diagnostica", "hipotesis diagnostica", "diagnosticos"),
    "indicaciones": ("indicaciones", "plan", "se indica", "indico", "tratamiento"),
}
PISTAS = {
    "examen_fisico": ("presion arterial", "pa ", "frecuencia cardiaca", "fc ", "saturacion", "temperatura",
                      "auscultacion", "abdomen", "murmullo", "ruidos cardiacos", "lucido", "hidratado"),
    "diagnostico": ("diagnostico", "impresion", "compatible con", "se plantea"),
    "indicaciones": ("control en", "se indica", "indico", "receta", "reposo", "derivar", "interconsulta",
                     "solicitar", "se solicita", "suspender", "continuar con"),
}
_FRASES = re.compile(r"(?<=[.!?;])\s+|\n+")


def _seccion_de(frase: str) -> tuple[str | None, str]:
    """Devuelve (sección, frase sin el encabezado) si la frase abre una sección."""
    n = normalize(frase)
    for sec, heads in ENCABEZADOS.items():
        for h in heads:
            if n.startswith(h):
                resto = frase[len(h):].lstrip(" :.-,")
                return sec, (resto if n[len(h):len(h) + 1] in (":", " ", ".", "-", ",", "") else frase)
    for sec, pistas in PISTAS.items():
        if any(p in n for p in pistas):
            return sec, frase
    return None, frase


def por_reglas(texto: str) -> dict[str, str]:
    actual, partes = "anamnesis", {k: [] for k in SECCIONES}
    for frase in (f.strip() for f in _FRASES.split(texto or "") if f.strip()):
        sec, limpia = _seccion_de(frase)
        actual = sec or actual
        if limpia:
            partes[actual].append(limpia)
    return {k: " ".join(v).strip() for k, v in partes.items()}


def _todo_textual(secciones: dict[str, str], original: str) -> bool:
    """Valida que cada frase propuesta por el modelo esté en la transcripción original."""
    base = normalize(" ".join(original.split()))
    for v in secciones.values():
        for frase in (f.strip(" .;") for f in _FRASES.split(v or "") if f.strip(" .;")):
            if normalize(" ".join(frase.split())) not in base:
                return False
    return True


def por_modelo(texto: str) -> dict[str, str] | None:
    tarea = ("Ordena la transcripción de una consulta en las secciones anamnesis, examen_fisico, diagnostico "
             "e indicaciones. Copia frases textuales de la transcripción, sin agregar, corregir ni resumir. "
             "Si una sección no se dictó, déjala vacía. Responde solo JSON con esas cuatro claves.")
    raw = llm.complete(prompts.para_modulo(1, tarea), texto[:6000], max_tokens=1200, clinical=True, timeout=20)
    if not raw:
        return None
    try:
        data = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
        out = {k: str(data.get(k) or "").strip() for k in SECCIONES}
    except (ValueError, AttributeError):
        return None
    return out if _todo_textual(out, texto) else None


def estructurar(texto: str) -> dict:
    secciones, origen = None, "reglas"
    if llm.enabled(clinical=True):
        secciones = por_modelo(texto)
        origen = "modelo local (validado: solo frases textuales)" if secciones else "reglas"
    secciones = secciones or por_reglas(texto)
    return {
        "secciones": [{"id": k, "titulo": t, "texto": secciones.get(k, ""),
                       "faltante": None if secciones.get(k) else "No se dictó información para esta sección."}
                      for k, t in SECCIONES.items()],
        "origen": origen,
        "estado": "borrador",
        "aviso": "Borrador generado automáticamente desde el dictado. Revise, corrija y firme antes de registrarlo.",
    }
