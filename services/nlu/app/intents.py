"""Catálogo de intenciones. Es la fuente única que usan Rasa (vía nlu.yml),
el LLM (como lista cerrada de etiquetas) y el clasificador de respaldo."""
from __future__ import annotations

from medicai_common.textutil import normalize

INTENTS: dict[str, str] = {
    "saludo": "El usuario saluda o inicia la conversación.",
    "despedida": "El usuario se despide.",
    "agradecer": "El usuario agradece.",
    "menu": "Quiere ver el menú u opciones disponibles.",
    "ayuda": "No sabe cómo usar el asistente.",
    "cancelar": "Quiere detener o salir del trámite en curso.",
    "afirmar": "Responde que sí.",
    "negar": "Responde que no.",
    "emergencia": "Describe una emergencia vital o pide ayuda urgente.",
    "agendar_cita": "Quiere reservar una hora de atención primaria en su CESFAM.",
    "ver_citas": "Quiere consultar las horas que ya tiene agendadas.",
    "cancelar_cita": "Quiere cancelar o reagendar una hora existente.",
    "recordatorio_medicamento": "Quiere que le recuerden tomar un medicamento.",
    "ver_recordatorios": "Quiere ver, cambiar o eliminar sus recordatorios de medicamentos.",
    "orientacion_sintomas": "Describe síntomas o malestar y necesita saber dónde o cuándo consultar.",
    "guia_ruta": "Tiene una interconsulta, orden de exámenes, receta o derivación y no sabe qué hacer; "
                 "o necesita un especialista (nivel secundario).",
    "farmacia": "Pregunta por disponibilidad de medicamentos o por retirar su receta en la farmacia del CESFAM.",
    "ver_retiros": "Quiere ver sus próximos retiros de medicamentos.",
    "resultados_examenes": "Pregunta por el resultado de un examen de laboratorio o imagen (radiografía, ecografía, etc.).",
    "tramites_fonasa": "Pregunta por FONASA: bonos, certificado de afiliación, GES/AUGE, licencias médicas o devoluciones.",
    "salud_mental": "Expresa ánimo bajo, ansiedad, tristeza, estrés o insomnio, sin riesgo vital inmediato.",
    "modo_cuidador": "Quiere gestionar horas, resultados o recordatorios de un familiar o persona a su cargo.",
    "hablar_persona": "Quiere hablar con una persona, un ejecutivo, o dejar un reclamo o sugerencia.",
    "info_hospital": "Pregunta por dirección, horarios, cómo llegar o estacionamiento del hospital.",
    "visitas": "Pregunta por horarios de visita o acompañantes de pacientes hospitalizados.",
    "preparacion_examenes": "Pregunta cómo prepararse para un examen (ayuno, muestras).",
}

# Clasificador de respaldo por palabras clave: solo opera si Rasa y el LLM no están
# disponibles, para que el sistema siga funcionando en modo degradado.
KEYWORDS: list[tuple[str, list[str]]] = [
    ("modo_cuidador", ["modo cuidador", "cuidador", "mi papa", "mi mama", "mi madre", "mi padre", "mi abuel",
                       "por mi familiar", "a nombre de"]),
    ("hablar_persona", ["hablar con una persona", "hablar con alguien", "humano", "ejecutivo", "reclamo",
                        "sugerencia", "llamada", "operador", "persona real"]),
    ("preparacion_examenes", ["preparacion", "ayuno", "en ayunas", "como me preparo"]),
    ("resultados_examenes", ["resultado", "laboratorio", "radiografia", "ecografia", "tomografia", "biopsia",
                             "scanner", "escaner", "mis examenes"]),
    ("tramites_fonasa", ["fonasa", "bono", "auge", "licencia", "afiliacion", "devolucion", "tramite", "copago"]),
    ("salud_mental", ["ansiedad", "ansioso", "ansiosa", "triste", "animo", "depresion", "deprimid", "estres",
                      "estresad", "insomnio", "no puedo dormir", "llorar", "no puedo mas", "angustia"]),
    ("visitas", ["visita", "acompanante", "horario de visita"]),
    ("info_hospital", ["direccion", "como llegar", "estacionamiento", "micro", "donde queda", "horario de atencion",
                       "horarios"]),
    ("ver_citas", ["mis citas", "mis horas", "cuando es mi hora", "ver mi cita"]),
    ("cancelar_cita", ["cancelar mi hora", "anular mi hora", "reagendar", "reprogramar", "cambiar mi hora",
                       "cambiar hora", "no podre ir"]),
    ("ver_recordatorios", ["mis recordatorios", "ver recordatorios", "gestionar recordatorios",
                           "eliminar recordatorio"]),
    ("ver_retiros", ["mis retiros", "ver retiros", "proximo retiro"]),
    ("agendar_cita", ["agendar", "pedir hora", "sacar hora", "una hora", "cita medica", "reservar hora"]),
    ("recordatorio_medicamento", ["recordatorio", "recuerdame", "recordar", "alarma", "se me olvida"]),
    ("farmacia", ["stock", "farmacia", "retirar", "retiro", "disponible", "hay remedio"]),
    ("guia_ruta", ["guia de ruta", "interconsulta", "derivacion", "derivaron", "orden de examen", "ges",
                   "especialista"]),
    ("orientacion_sintomas", ["orientacion", "sintoma", "me duele", "dolor", "fiebre", "tos", "me siento mal",
                              "diarrea", "vomito", "picazon", "mareo"]),
    ("menu", ["menu", "opciones", "inicio"]),
    ("ayuda", ["ayuda", "comandos", "como funciona"]),
    ("cancelar", ["cancelar", "salir", "olvidalo"]),
    ("agradecer", ["gracias"]),
    ("despedida", ["chao", "adios", "hasta luego"]),
    ("saludo", ["hola", "buenas", "buenos dias", "saludos", "wena"]),
    ("afirmar", ["si", "dale", "ok", "claro"]),
    ("negar", ["no"]),
]


def keyword_intent(text: str) -> str | None:
    t = f" {normalize(text)} "
    for intent, kws in KEYWORDS:
        for kw in kws:
            if len(kw) <= 3:
                if f" {kw} " in t:
                    return intent
            elif kw in t:
                return intent
    return None
