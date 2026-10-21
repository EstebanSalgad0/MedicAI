"""Orientación inicial de síntomas: sugiere el nivel de atención, no diagnostica."""
from __future__ import annotations

from medicai_common.contracts import DialogRequest, DialogResponse, DomainEvent, Handoff, reply
from medicai_common.matching import choice, remember_menu
from medicai_common.messages import DISCLAIMER, buttons, lst, text
from medicai_common.safety import EMERGENCY_TEXT, MENTAL_HEALTH_TEXT, red_flag
from medicai_common.textutil import normalize

from . import reglas

FOOTER = "Orientación • MedicAI"
CATEGORIAS = [
    ("respiratorio", "🫁 Respiratorias"),
    ("bucal", "🦷 Bucales"),
    ("infeccioso", "🦠 Infecciosas"),
    ("cardiovascular", "❤️ Cardiovasculares"),
    ("metabolico", "⚖️ Metabólicas"),
    ("neurologico", "🧠 Neurológicas"),
    ("musculoesqueletico", "💪 Musculares y huesos"),
    ("saludmental", "🧘 Salud mental"),
    ("dermatologico", "🩹 Piel"),
    ("otorrinolaringologico", "👂 Ojos, oídos, nariz"),
    ("ginecologico", "♀️ Ginecológicas/urinarias"),
    ("digestivo", "🍽️ Digestivas"),
]
NOMBRE = {k: v.split(" ", 1)[1] for k, v in CATEGORIAS}

# Traducción del texto libre de nivel de alerta de las reglas a 4 niveles de triage.
NIVELES = {
    "urgencia": ("🔴", "Urgencia", "Acude hoy a un SAPU/SAR o urgencia. Si empeora, llama al 131."),
    "prioritario": ("🟠", "Atención prioritaria", "Pide una hora de morbilidad en tu CESFAM para hoy o mañana."),
    "control": ("🟡", "Consulta en tu CESFAM", "Agenda una hora en tu CESFAM en los próximos días."),
    "autocuidado": ("🟢", "Autocuidado", "Puedes manejarlo en casa; consulta si no mejora o aparecen nuevos síntomas."),
}


def nivel_triage(nivel_texto: str) -> str:
    t = normalize(nivel_texto)
    if any(k in t for k in ("urgen", "inmediat", "emergencia")):
        return "urgencia"
    if any(k in t for k in ("24 h", "pronta", "pronto", "hoy")):
        return "prioritario"
    if "autocuidado" in t or "casa" in t:
        return "autocuidado"
    return "control"


def _match_text(raw: str) -> str:
    # Las reglas mezclan términos con y sin tilde: se evalúan ambas variantes.
    return f"{raw.lower()} || {normalize(raw)}"


def detectar(categoria: str, raw: str) -> list[str]:
    t = _match_text(raw)
    vistos, out = set(), []
    for s in reglas.SINTOMAS_CONOCIDOS.get(categoria, []):
        k = normalize(s)
        if s.lower() in t and k not in vistos:
            vistos.add(k)
            out.append(s)
    return out


def ask_category(page: int = 1) -> DialogResponse:
    if page == 1:
        opts = [(f"ori:cat:{k}", v) for k, v in CATEGORIAS[:9]] + [("ori:cat:page2", "➡️ Ver más")]
        body = ("🩺 *Orientación de síntomas*\n\n"
                "Te ayudo a saber *dónde y cuándo* consultar. No es un diagnóstico.\n"
                "En una emergencia llama al *131*.\n\n¿Qué tipo de molestia tienes?")
    else:
        opts = [(f"ori:cat:{k}", v) for k, v in CATEGORIAS[9:]] + [("ori:cat:page1", "⬅️ Volver")]
        body = "Otras categorías:"
    msg = lst(body, opts, FOOTER, "Ver categorías")
    return reply(msg, state=remember_menu({"step": "category"}, msg))


def ask_symptoms(cat: str) -> DialogResponse:
    ejemplo = reglas.EJEMPLOS_SINTOMAS.get(cat, "")
    return reply(text(f"✍️ Describe tus síntomas *{NOMBRE[cat].lower()}* con tus palabras.\n"
                      f"_Ejemplo: {ejemplo}_"), state={"step": "symptoms", "categoria": cat})


def result(state: dict) -> DialogResponse:
    cat, raw = state["categoria"], state["texto"]
    fn = getattr(reglas, f"diagnostico_{cat}", None)
    salida = fn(_match_text(raw)) if fn else (None, "", "")
    diag, nivel_txt, reco = (list(salida) + ["", ""])[:3]
    nivel = nivel_triage(nivel_txt) if diag else "control"
    icon, nombre_nivel, accion = NIVELES[nivel]
    cuerpo = [f"{icon} *Nivel de atención sugerido: {nombre_nivel}*", accion, ""]
    if diag:
        cuerpo += [f"Tus síntomas podrían relacionarse con: _{diag}_ (orientativo, lo confirma un profesional).",
                   "", reco]
    else:
        cuerpo.append("Con lo que me contaste no puedo orientarte con precisión; lo mejor es que te evalúe un profesional.")
    general = reglas.RECOMENDACIONES_GENERALES.get(cat, reglas.RECOMENDACIONES_GENERALES["default"])
    cuerpo += ["", "*Recomendaciones generales:*", general]
    msgs = [text("\n".join(cuerpo) + DISCLAIMER)]
    handoff_opts = []
    if nivel in ("prioritario", "control"):
        handoff_opts.append(("agd:start", "🗓️ Agendar hora"))
    if nivel == "urgencia":
        handoff_opts.append(("der:type:urgente", "🚑 ¿Dónde consultar?"))
    if handoff_opts:
        handoff_opts.append(("sys:menu", "🏠 Menú"))
        msgs.append(buttons("¿Te ayudo con algo más?", handoff_opts, FOOTER))
    ev = DomainEvent(type="triage_completed", props={"categoria": cat, "nivel": nivel,
                                                     "sintomas_detectados": len(state.get("detectados", [])),
                                                     "regla_aplicada": bool(diag)})
    return reply(*msgs, state=None, resolved=True, events=[ev])


def handle(req: DialogRequest) -> DialogResponse:
    flag = red_flag(req.text)
    if flag:
        body = MENTAL_HEALTH_TEXT if flag == "salud_mental" else EMERGENCY_TEXT
        return reply(text(body), state=None, resolved=True,
                     events=[DomainEvent(type="red_flag_detected", props={"tipo": flag, "origen": "orientacion"})])

    state = dict(req.state)
    opt = choice(req)
    if req.start:
        cat = (req.entities or {}).get("categoria_sintoma")
        return ask_symptoms(cat) if cat in NOMBRE else ask_category()

    step = state.get("step")
    if opt and opt.startswith("ori:cat:"):
        arg = opt.split(":")[2]
        if arg in ("page1", "page2"):
            return ask_category(int(arg[-1]))
        if arg in NOMBRE:
            return ask_symptoms(arg)
    if step == "category":
        return ask_category()
    if step == "symptoms":
        if len(req.text.strip()) < 3:
            return ask_symptoms(state["categoria"])
        detectados = detectar(state["categoria"], req.text)
        state.update(texto=req.text, detectados=detectados, step="confirm")
        lista = "\n".join(f"• {d}" for d in detectados) if detectados else "• (no reconocí síntomas específicos)"
        msg = buttons(f"🔎 Entendí estos síntomas:\n{lista}\n\n¿Es correcto?",
                      [("ori:confirm:yes", "✅ Sí"), ("ori:confirm:no", "✏️ Corregir")], FOOTER)
        return reply(msg, state=remember_menu(state, msg))
    if step == "confirm":
        if opt == "ori:confirm:yes":
            return result(state)
        if opt == "ori:confirm:no":
            return reply(text("Está bien, cuéntame de nuevo tus síntomas con más detalle:"),
                         state={"step": "symptoms", "categoria": state["categoria"]})
    if opt == "agd:start":
        return reply(state=None, handoff=Handoff(service="agendamiento", intent="agendar_cita"))
    return ask_category()
