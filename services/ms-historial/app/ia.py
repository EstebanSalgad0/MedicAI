"""Apoyo diagnóstico con el modelo local (opcional).

El modelo solo puede proponer hipótesis fundadas en registros que existen: cada propuesta
debe citar identificadores de registros entregados en el contexto. Lo que no cita un
registro válido se descarta (control anti-alucinación). Nunca se usa un proveedor externo
con datos clínicos (`clinical=True`).
"""
from __future__ import annotations

import json
import logging

from medicai_common import llm, prompts

from .clinica import _describe
from .fuentes import Registro

log = logging.getLogger("historial.ia")


def disponible() -> bool:
    return llm.enabled(clinical=True)


def hipotesis(cuadro: str, registros: dict[str, Registro]) -> list[dict]:
    if not disponible() or not registros:
        return []
    contexto = "\n".join(f"[{rid}] {_describe(r)} {r.cita.texto()}" for rid, r in list(registros.items())[:120])
    tarea = ("Con el cuadro clínico y los registros entregados, propone hasta 3 hipótesis a considerar y exámenes "
             "sugeridos. Cada hipótesis debe citar los identificadores de los registros en que se basa. "
             'Responde solo JSON: [{"hipotesis": "...", "registros": ["id", ...], "examenes": ["...", ...]}]. '
             "Si los registros no respaldan ninguna hipótesis, responde [].")
    raw = llm.complete(prompts.para_modulo(1, tarea), f"Cuadro clínico: {cuadro}\n\nRegistros:\n{contexto}",
                       max_tokens=700, clinical=True, timeout=20)
    if not raw:
        return []
    try:
        data = json.loads(raw[raw.index("["): raw.rindex("]") + 1])
    except ValueError:
        log.warning("Respuesta del modelo no es JSON")
        return []
    out = []
    for h in data[:3] if isinstance(data, list) else []:
        ids = [i for i in (h.get("registros") or []) if i in registros]
        if not ids or not h.get("hipotesis"):
            continue  # sin fuente válida: se descarta
        texto = str(h["hipotesis"]).strip()
        out.append({
            "codigo": "IA-LOCAL",
            "hipotesis": texto if texto.lower().startswith("hipótesis") else f"Hipótesis a considerar: {texto}",
            "fundamentos": [{"texto": _describe(registros[i]), "cita": registros[i].cita.texto(), "registro": i}
                            for i in ids],
            "examenes_sugeridos": [str(e) for e in (h.get("examenes") or [])][:6],
            "urgente": False, "origen": "modelo local (citas verificadas)",
            "nota": "Requiere confirmación del médico tratante.",
        })
    return out
