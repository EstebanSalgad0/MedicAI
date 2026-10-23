"""«Tengo síntomas»: triaje informativo con reglas determinísticas.

Edad → síntomas (varios) → duración → una pregunta directa de alarma → nivel
(alto / medio / bajo) con una acción concreta. No diagnostica: solo sugiere dónde
y cuándo consultar.
"""
from __future__ import annotations

from medicai_common.contracts import DialogRequest, DialogResponse, DomainEvent, reply
from medicai_common.messages import buttons, lst, text
from medicai_common.safety import EMERGENCY_TEXT
from medicai_common.textutil import normalize, now_local

FOOTER = "Orientación • MedicAI"
NO_DX = "\n\n_Esto es orientación, no un diagnóstico._"

EDADES = [("0-5", "👶 0 a 5 años"), ("6-17", "🧒 6 a 17 años"), ("18-59", "🧑 18 a 59 años"), ("60+", "👴 60 años o más")]
SINTOMAS = [
    ("fiebre", "🌡️ Fiebre", ("fiebre", "temperatura", "afiebrad")),
    ("tos", "😷 Tos", ("tos",)),
    ("cabeza", "🤕 Dolor de cabeza", ("dolor de cabeza", "cabeza", "jaqueca", "migrana")),
    ("abdominal", "🫃 Dolor abdominal", ("guata", "abdom", "estomago", "barriga")),
    ("garganta", "🗣️ Dolor de garganta", ("garganta",)),
    ("muscular", "💪 Dolor muscular", ("muscul", "cuerpo cortado", "dolor de cuerpo")),
    ("congestion", "🤧 Congestión nasal", ("congestion", "nariz tapada", "mocos", "resfri")),
    ("gastro", "🤢 Vómitos o diarrea", ("vomit", "diarrea", "nausea")),
    ("sarpullido", "🔴 Sarpullido", ("sarpullido", "ronchas", "manchas en la piel", "granitos", "alergia en la piel")),
    ("herida", "🩹 Herida leve", ("herida", "corte", "rasm")),
]
NOMBRE = {k: t.split(" ", 1)[1] for k, t, _ in SINTOMAS}
DURACIONES = [("lt24", "Menos de 24 h"), ("1-3", "1 a 3 días"), ("gt3", "Más de 3 días")]

NIVELES = {  # nivel del flujo → nivel del tablero (urgencia / prioritario / control / autocuidado)
    "alto": ("🟠", "ALTO", "Necesitas una *evaluación presencial*.", "prioritario"),
    "medio": ("🟡", "MEDIO", "Te recomiendo atenderte en tu *CESFAM* dentro de las próximas *24 a 48 horas*.", "control"),
    "bajo": ("🟢", "BAJO", "Puedes manejarlo en casa con autocuidado.", "autocuidado"),
}


def detectar(raw: str) -> list[str]:
    t = normalize(raw)
    return [k for k, _, kws in SINTOMAS if any(w in t for w in kws)]


def ask_age(state: dict) -> DialogResponse:
    previos = f"\n_Anoté: {', '.join(NOMBRE[s].lower() for s in state.get('sintomas', []))}._" \
        if state.get("sintomas") else ""
    msg = lst("🩺 *Te oriento sobre dónde y cuándo consultar.*\n"
              "Si es una emergencia llama al *SAMU 131*.\n\n¿Qué edad tiene la persona con síntomas?" + previos,
              [(f"ori:t:edad:{k}", v) for k, v in EDADES], FOOTER, "Elegir edad")
    return reply(msg, state={**state, "step": "t_edad", "_menu": msg.model_dump()})


def ask_symptoms(state: dict) -> DialogResponse:
    sel = state.get("sintomas", [])
    restantes = [(f"ori:t:sin:{k}", t) for k, t, _ in SINTOMAS if k not in sel]
    if sel:
        body = ("Anoté: *" + ", ".join(NOMBRE[s].lower() for s in sel) + "*.\n\n"
                "¿Tiene otro síntoma? Elígelo, o toca *Ya está* para seguir.")
        opts = [("ori:t:sin:listo", "✅ Ya está")] + restantes[:9]
    else:
        body = "¿Qué síntomas tiene? Elige uno; después puedes sumar más.\n_También puedes escribirlos, ej: fiebre y tos._"
        opts = restantes
    msg = lst(body, opts, FOOTER, "Elegir síntomas")
    return reply(msg, state={**state, "step": "t_sintomas", "_menu": msg.model_dump()})


def ask_duration(state: dict) -> DialogResponse:
    msg = buttons("¿Hace cuánto tiempo empezaron los síntomas?",
                  [(f"ori:t:dur:{k}", v) for k, v in DURACIONES], FOOTER)
    return reply(msg, state={**state, "step": "t_duracion", "_menu": msg.model_dump()})


def ask_alarm(state: dict) -> DialogResponse:
    msg = buttons("Una última pregunta importante:\n\n*¿Tiene dificultad para respirar, dolor de pecho, fiebre muy alta "
                  "que no baja, o está confundido/a o muy dormido/a?*",
                  [("ori:t:alarma:si", "Sí"), ("ori:t:alarma:no", "No")], FOOTER)
    return reply(msg, state={**state, "step": "t_alarma", "_menu": msg.model_dump()})


def nivel(edad: str, sintomas: list[str], duracion: str) -> str:
    n = len(sintomas)
    if edad == "0-5" or duracion == "gt3" or n >= 5:
        return "alto"
    if n <= 2 and duracion == "lt24":
        return "bajo"
    return "medio"


def result(state: dict, alarma: bool) -> DialogResponse:
    edad, sintomas, dur = state["edad"], state.get("sintomas", []), state["duracion"]
    if alarma:
        ev = DomainEvent(type="triage_completed", props={"nivel": "urgencia", "flujo": "rapido", "edad": edad,
                                                         "sintomas": len(sintomas), "alarma": True})
        return reply(text(EMERGENCY_TEXT), state=None, resolved=True,
                     events=[ev, DomainEvent(type="red_flag_detected", props={"tipo": "urgencia", "origen": "triaje"})])
    lvl = nivel(edad, sintomas, dur)
    icon, nombre, accion, tablero = NIVELES[lvl]
    lineas = [f"{icon} *Nivel {nombre}*", accion]
    if lvl == "bajo":
        lineas += ["", "*Qué hacer en casa:*", "• Reposo e hidratación (agua, caldos).",
                   "• Controla la fiebre con medidas físicas y el antipirético que ya uses habitualmente.",
                   "", "*Consulta de inmediato si aparece:* dificultad para respirar, dolor de pecho, fiebre que no baja, "
                   "decaimiento marcado o confusión.",
                   "", "Si en *48 horas* no mejora, consulta en tu CESFAM."]
    ahora = now_local()
    if edad == "0-5" and (ahora.weekday() >= 5 or ahora.hour >= 20 or ahora.hour < 8):
        lineas += ["", "🌙 Al ser un niño o niña pequeño y fuera del horario del CESFAM, acude al *SAPU/SAR* de tu comuna "
                   "o a la urgencia de la red."]
    resumen = f"\n\n_Síntomas: {', '.join(NOMBRE[s].lower() for s in sintomas)} · {dict(DURACIONES)[dur].lower()}._"
    if lvl == "alto":
        opts = [("agd:start", "📅 Agendar una hora"), ("der:type:urgente", "🚑 ¿Dónde consultar?")]
    elif lvl == "medio":
        opts = [("agd:place:cesfam", "🏠 Hora en mi CESFAM"), ("ori:cat:page1", "📝 Más detalle")]
    else:
        opts = [("agd:place:cesfam", "🏠 Hora en mi CESFAM")]
    msg = buttons("\n".join(lineas) + resumen + NO_DX, opts, FOOTER)
    ev = DomainEvent(type="triage_completed", props={"nivel": tablero, "flujo": "rapido", "edad": edad,
                                                     "sintomas": len(sintomas), "duracion": dur, "alarma": False})
    return reply(msg, state=None, resolved=True, events=[ev])


def handle(req: DialogRequest, opt: str | None, state: dict) -> DialogResponse:
    step = state.get("step")
    if opt and opt.startswith("ori:t:"):
        _, _, kind, val = opt.split(":", 3)
        if kind == "edad":
            state["edad"] = val
            return ask_symptoms(state) if not state.get("sintomas") else ask_duration(state)
        if kind == "sin":
            if val == "listo":
                return ask_duration(state) if state.get("sintomas") else ask_symptoms(state)
            state["sintomas"] = list(dict.fromkeys(state.get("sintomas", []) + [val]))
            return ask_symptoms(state)
        if kind == "dur":
            state["duracion"] = val
            return ask_alarm(state)
        if kind == "alarma" and state.get("edad") and state.get("duracion"):
            return result(state, val == "si")
    # texto libre dentro del flujo
    if step == "t_sintomas":
        nuevos = detectar(req.text)
        if nuevos:
            state["sintomas"] = list(dict.fromkeys(state.get("sintomas", []) + nuevos))
        return ask_symptoms(state)
    if step == "t_edad":
        return ask_age(state)
    if step == "t_duracion":
        return ask_duration(state)
    if step == "t_alarma":
        return ask_alarm(state)
    return ask_age({"sintomas": detectar(req.text)})


def start(req: DialogRequest) -> DialogResponse:
    return ask_age({"sintomas": detectar(req.text)})
