"""Catálogo de prestaciones: CESFAM (APS) y Hospital Regional de Talca (especialidades).

Las horas de APS se agendan en el CESFAM del paciente. Las especialidades del
hospital (nivel secundario) requieren, salvo excepciones, una interconsulta del
CESFAM: si el paciente no la tiene, el bot le explica cómo obtenerla.
"""
from medicai_common.centros import CENTRO_NOMBRE, CENTROS, HOSPITAL  # noqa: F401

PRESTACIONES: list[tuple[str, str]] = [
    ("medicina_general", "🩺 Medicina general"),
    ("control_cronico", "❤️ Control crónico (PSCV)"),
    ("enfermeria", "💉 Enfermería"),
    ("matrona", "🤰 Matrona"),
    ("nino_sano", "👶 Control niño sano"),
    ("salud_mental", "🧠 Salud mental"),
    ("kinesiologia", "🏋️ Kinesiología"),
    ("odontologia", "🦷 Odontología"),
    ("nutricion", "🥗 Nutrición"),
    ("toma_muestras", "🧪 Toma de muestras"),
    ("vacunacion", "💉 Vacunación"),
    ("domiciliaria", "🏠 Atención domiciliaria"),
    ("podologia", "🦶 Podología"),
]
ESPECIALIDADES_HRT: list[tuple[str, str]] = [
    ("medicina_general", "🩺 Medicina general"),
    ("cardiologia", "❤️ Cardiología"),
    ("traumatologia", "🦴 Traumatología"),
    ("pediatria", "👶 Pediatría"),
    ("ginecologia", "♀️ Ginecología"),
    ("oftalmologia", "👁️ Oftalmología"),
    ("kinesiologia", "🏋️ Kinesiología"),
]
# Especialidades que en la red pública se atienden con interconsulta del CESFAM
REQUIERE_DERIVACION = {"cardiologia", "traumatologia", "pediatria", "ginecologia", "oftalmologia"}

PRESTACION_NOMBRE = {k: v.split(" ", 1)[1] for k, v in PRESTACIONES + ESPECIALIDADES_HRT}
SOLO_HOSPITAL = {k for k, _ in ESPECIALIDADES_HRT} - {k for k, _ in PRESTACIONES}

HRT = HOSPITAL[0]
HORARIOS = ["08:30", "09:30", "10:30", "11:30", "14:30", "15:30", "16:30"]
HORARIOS_HRT = ["08:00", "08:40", "09:20", "10:00", "10:40", "11:20", "12:00", "14:00", "14:40", "15:20", "16:00"]
DIAS_HABILES_A_OFRECER = 7

# Palabras que sugieren un problema de salud con garantía GES (orientativo, no exhaustivo)
GES_PALABRAS = {
    "catarata": "cataratas", "cancer": "cáncer", "diabetes": "diabetes", "hipertension": "hipertensión",
    "infarto": "infarto", "epoc": "EPOC", "asma": "asma", "depresion": "depresión", "artrosis": "artrosis",
    "vicio de refraccion": "vicio de refracción", "estrabismo": "estrabismo", "epilepsia": "epilepsia",
    "hipoacusia": "hipoacusia", "marcapaso": "trastornos de conducción (marcapaso)",
}

# Dotación por establecimiento: qué profesional atiende cada prestación y en qué box.
# Datos de demostración: reemplazar por la programación real de cada centro (o integrarla).
_NOMBRES_PRO = ["Dra. Paula Ortiz", "Dr. Andrés Leiva", "E.U. Camila Reyes", "Mat. Daniela Vera", "Dra. Sofía Navarro",
                "Ps. Tomás Acuña", "Klgo. Felipe Araya", "Dr. Ignacio Paredes", "Nut. Valentina Cid",
                "TENS Rodrigo Salas", "E.U. Francisca Lagos", "Dra. Constanza Mella", "Pod. Javier Tapia"]


def dotacion(center_id: str) -> list[dict]:
    prestaciones = ESPECIALIDADES_HRT if center_id == HRT else PRESTACIONES
    offset = sum(map(ord, center_id)) % len(_NOMBRES_PRO)
    return [{"prestacion": k, "prestacion_nombre": PRESTACION_NOMBRE[k],
             "profesional": _NOMBRES_PRO[(i + offset) % len(_NOMBRES_PRO)],
             "box": f"{'Policlínico ' if center_id == HRT else 'Box '}{i + 1}"}
            for i, (k, _) in enumerate(prestaciones)]


# Prioridad en la lista de espera: la prioridad clínica prevalece sobre el orden de llegada
PRIORIDAD_NOMBRE = {0: "Orden de llegada", 1: "GES (garantía de oportunidad)", 2: "Prioridad clínica"}
