"""Catálogo de prestaciones de Atención Primaria y CESFAM piloto.

Se limita a prestaciones que se agendan en APS. Las atenciones de especialidad
(nivel secundario) no se agendan aquí: se gestionan como interconsulta en el
microservicio de derivación. Esto responde a la observación de ANID sobre la
delimitación entre APS y niveles secundarios.
"""

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
PRESTACION_NOMBRE = {k: v.split(" ", 1)[1] for k, v in PRESTACIONES}

from medicai_common.centros import CENTRO_NOMBRE, CENTROS  # noqa: F401,E402

HORARIOS = ["08:30", "09:30", "10:30", "11:30", "14:30", "15:30", "16:30"]
DIAS_HABILES_A_OFRECER = 7
