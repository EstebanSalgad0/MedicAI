"""Analítica conversacional para el modo gestión: «¿cómo va el ausentismo?» →
número clave, contexto (comparación y proyección) y sugerencia operativa.

Interpreta la pregunta por palabras clave (sin LLM, predecible y auditable) y
responde solo con datos agregados: nunca con datos de pacientes identificables.
"""
from __future__ import annotations

import os

from medicai_common.textutil import normalize

LINEA_BASE_AUSENTISMO = float(os.getenv("AUSENTISMO_LINEA_BASE", "0.20"))
META_AUSENTISMO = 0.10

DOMINIOS = [
    ("ausentismo", ("ausentismo", "inasistencia", "no show", "no asist", "fill", "recuper", "ausent")),
    ("camas", ("cama", "uci", "ocupacion", "tim", "hospitaliz")),
    ("urgencias", ("urgencia", "box", "espera media", "triage", "sapu")),
    ("listas", ("lista", "listas", "ges", "espera para")),
    ("pabellones", ("pabellon", "quirofano", "cirugia", "suspension")),
    ("chatbot", ("chatbot", "bot", "resolucion", "satisfaccion", "temas", "medicai", "desvio")),
]


def domain(question: str) -> str:
    t = normalize(question)
    return next((d for d, kws in DOMINIOS if any(k in t for k in kws)), "resumen")


def pct(x: float | None) -> str:
    return "—" if x is None else f"{x * 100:.1f} %".replace(".", ",")


def answer(question: str, snap: dict, agenda: list[dict] | None, today: dict | None, bot: dict) -> dict:
    d = domain(question)
    if d == "ausentismo":
        rates = [x["no_show_rate"] for x in (agenda or []) if x.get("no_show_rate") is not None]
        recuperadas = sum(x.get("gap_filled", 0) for x in (agenda or []))
        actual = (today or {}).get("no_show_rate")
        semana = sum(rates[-7:]) / len(rates[-7:]) if rates[-7:] else None
        previa = sum(rates[-14:-7]) / len(rates[-14:-7]) if rates[-14:-7] else None
        if semana is None:
            txt = ("📉 *Ausentismo:* aún no hay asistencia registrada en los últimos 14 días.\n\n"
                   "💡 Pide a los equipos marcar «Asistió / No asistió» en la Agenda para medirlo.")
        else:
            tendencia = "" if previa is None else (
                f" ({'baja' if semana < previa else 'sube'} desde {pct(previa)} la semana anterior)")
            proy = semana + (semana - previa) if previa is not None else semana
            txt = (f"📉 *Ausentismo últimos 7 días: {pct(semana)}*{tendencia}.\n\n"
                   f"• Hoy: {pct(actual)} · Línea base: {pct(LINEA_BASE_AUSENTISMO)} · Meta: ≤ {pct(META_AUSENTISMO)}\n"
                   f"• Proyección próxima semana: {pct(max(0.0, proy))}\n"
                   f"• Horas recuperadas por fill-the-gap (14 días): *{recuperadas}*\n\n"
                   + ("💡 Sugerencia: reforzar la confirmación del recordatorio de 24 h en las especialidades con más "
                      "inasistencia." if semana > META_AUSENTISMO else "✅ Bajo la meta: mantener recordatorios 48/24 h."))
        return {"domain": d, "answer": txt}
    if d == "camas":
        criticos = sorted(snap["camas"], key=lambda c: -c["pct"])[:3]
        txt = (f"🛏️ *Ocupación global: {pct(snap['ocupacion_global'])}* · *UCI: {snap['uci_disponibles']} camas libres* "
               f"({pct(snap['uci_pct'])} ocupada).\n\n"
               + "\n".join(f"• {c['servicio']}: {pct(c['pct'])} ({c['disponibles']} libres)" for c in criticos)
               + ("\n\n⚠️ Sugerencia: priorizar altas tempranas y evaluar apertura de camas TIM."
                  if snap["uci_pct"] >= 0.9 else "\n\n💡 Sugerencia: anticipar altas de 24–48 h en los servicios sobre 90 %."))
        return {"domain": d, "answer": txt}
    if d == "urgencias":
        u = snap["urgencias"]
        sobre = u["espera_media_min"] > u["meta_min"]
        txt = (f"🚑 *{u['en_espera']} pacientes en espera* en urgencia.\n\n"
               f"• Espera media: {u['espera_media_min']} min (meta < {u['meta_min']} min){' ⚠️' if sobre else ' ✅'}\n"
               f"• Box de observación: {u['box_ocupados']}/{u['box_observacion']} ({pct(u['box_pct'])})\n"
               f"• Pacientes esperando cama (boarding): {u['boarding']}\n"
               f"• Hora de más llegadas: {u['pico_hora']}\n\n"
               + ("💡 Sugerencia: reforzar el box de categorización antes del peak." if sobre
                  else "✅ Dentro de la meta."))
        return {"domain": d, "answer": txt}
    if d == "listas":
        listas = snap["listas_espera"]
        top = sorted(listas["por_especialidad"], key=lambda x: -x["mediana_dias"])[:3]
        txt = (f"⏳ *{listas['pacientes']:,} pacientes en lista de espera*".replace(",", ".")
               + f" · mediana {listas['mediana_dias']} días · cumplimiento GES {pct(listas['cumplimiento_ges'])}.\n\n"
               "Mayor espera:\n" + "\n".join(f"• {x['especialidad']}: {x['mediana_dias']} días" for x in top)
               + "\n\n💡 Sugerencia: usar fill-the-gap en estas especialidades para recuperar cupos liberados.")
        return {"domain": d, "answer": txt}
    if d == "pabellones":
        p = snap["pabellones"]
        txt = (f"🔪 *Utilización de pabellones: {pct(p['utilizacion'])}* ({p['pabellones']} pabellones).\n\n"
               f"• Cirugías programadas hoy: {p['cirugias_programadas']} · Suspensiones: {p['suspensiones']}\n"
               f"• Puntualidad de primera hora: {pct(p['puntualidad_primera_hora'])}\n\n"
               "💡 Sugerencia: confirmar pacientes del día siguiente por WhatsApp para bajar suspensiones.")
        return {"domain": d, "answer": txt}
    if d == "chatbot":
        temas = ", ".join(t["intent"] for t in bot["temas"][:3]) or "sin datos"
        sat = bot["satisfaction"]["value"]
        txt = (f"🤖 *Auto-resolución del chatbot: {pct(bot['auto_resolution']['value'])}* (meta ≥ 80 %).\n\n"
               f"• Temas más consultados: {temas}\n"
               f"• Satisfacción: {'—' if sat is None else f'{sat:.1f}'.replace('.', ',')} / 5\n"
               f"• Consultas desviadas a APS: {bot['desvio_aps_total']}\n"
               f"• Derivaciones a una persona: {bot['handoffs']}")
        return {"domain": d, "answer": txt}
    txt = (f"📊 *Resumen de hoy*\n\n• Ocupación de camas: {pct(snap['ocupacion_global'])} · UCI libres: "
           f"{snap['uci_disponibles']}\n• Urgencia: {snap['urgencias']['en_espera']} en espera, "
           f"{snap['urgencias']['espera_media_min']} min de espera media\n• Ausentismo hoy: "
           f"{pct((today or {}).get('no_show_rate'))}\n• Auto-resolución del chatbot: "
           f"{pct(bot['auto_resolution']['value'])}\n\nPuedes preguntarme por ausentismo, camas, urgencias, "
           "listas de espera, pabellones o el chatbot.")
    return {"domain": "resumen", "answer": txt}
