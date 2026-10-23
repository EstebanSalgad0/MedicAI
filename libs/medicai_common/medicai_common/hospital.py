"""Datos de contacto e información práctica del Hospital Regional de Talca.

⚠️ Valores tomados de la especificación funcional (v1.0). Deben verificarse con el
hospital antes de usarse con pacientes: la tarjeta de emergencia muestra la dirección.
Cada valor se puede reemplazar desde el .env sin tocar código.
"""
from __future__ import annotations

import os

NOMBRE = "Hospital Regional de Talca"
DIRECCION = os.getenv("HOSPITAL_DIRECCION", "Av. Circunvalación Oriente s/n")
MESA_AYUDA = os.getenv("HOSPITAL_MESA_AYUDA", "(71) 2 000 000")
MESA_HORARIO = os.getenv("HOSPITAL_MESA_HORARIO", "lun-vie 08:00-17:00")
TELEFONO_UCI = os.getenv("HOSPITAL_TELEFONO_UCI", "(71) 2 000 100")

INFO = (
    f"🏥 *{NOMBRE}*\n"
    f"📍 {DIRECCION}\n"
    "🕗 Admisión: lun-vie 07:30-17:00\n"
    "🚑 Urgencias: 24/7\n"
    "🚌 Micros: 101, 103, 105\n"
    "🅿️ Estacionamiento: acceso poniente\n"
    "♿ Accesibilidad universal"
)
VISITAS = (
    "👥 *Visitas y acompañantes*\n\n"
    "• *Hospitalización:* 2 acompañantes, de 15:00 a 20:00.\n"
    f"• *UCI:* horario especial acordado con el equipo tratante, tel. {TELEFONO_UCI}.\n"
    "• Retira tu *carnet de acompañamiento* en Admisión."
)
PREPARACION = (
    "🧪 *Preparación para exámenes*\n\n"
    "• *Perfil bioquímico o glucosa:* ayuno de 8 horas (solo agua).\n"
    "• *Ecografía abdominal:* ayuno de 6 horas.\n"
    "• *Orina:* primera orina de la mañana.\n"
    "• *No suspendas tus medicamentos* sin indicación médica.\n\n"
    "💡 Si tu examen requiere ayuno, conviene agendarlo en la mañana."
)
FARMACIA = "Farmacia Hospitalaria, módulo 1 (08:00-17:00). Lleva tu cédula de identidad."
