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
