"""Contenidos informativos de trámites FONASA.

⚠️ Basados en la especificación funcional (v1.0). Antes de usarlos con pacientes,
validar cada texto con FONASA y con la oficina de gestión del hospital: plazos,
canales de pago y procedimientos cambian. Dos ajustes respecto de la especificación:
  - Copago: desde septiembre de 2022 rige el Copago Cero para todos los tramos de
    FONASA en la red pública (la especificación decía «tramos A/B no pagan»).
  - GES: los plazos dependen de cada problema de salud; no hay un plazo único.
"""
from medicai_common import hospital

GUIA = "\n\n💬 Puedo guiarte paso a paso o, si prefieres, derivarte con un ejecutivo FONASA del hospital."

FONASA = {
    "bono": (
        "💳 Bono de atención",
        "💳 *Bono de atención*\n\n"
        "• En la *red pública* (hospital y CESFAM) los beneficiarios de FONASA *no pagan copago* (Copago Cero).\n"
        "• El bono se usa para atenderte con *prestadores privados en convenio* (Modalidad Libre Elección).\n\n"
        "*Cómo comprarlo:*\n"
        "1. Entra a *Mi FONASA* con tu ClaveÚnica y elige «Comprar bono».\n"
        "2. Paga en línea o en Caja Vecina, Sencillito o Multicaja.\n"
        "3. También puedes hacerlo en el *módulo FONASA del hospital* (08:00 a 15:00).",
    ),
    "certificado": (
        "📄 Certificado de afiliación",
        "📄 *Certificado de afiliación*\n\n"
        "1. Entra a *Mi FONASA* (fonasa.cl) con tu ClaveÚnica.\n"
        "2. Elige «Certificados» → «Certificado de afiliación».\n"
        "3. Descárgalo: es *gratis e inmediato*.",
    ),
    "ges": (
        "🛡️ Garantías GES/AUGE",
        "🛡️ *GES / AUGE (Garantías Explícitas en Salud)*\n\n"
        "• Cubre un listado de problemas de salud con *plazos máximos garantizados* para diagnóstico y "
        "tratamiento. Cada problema tiene su propio plazo.\n"
        "• Tu atención GES *no puede condicionarse a un pago*.\n"
        "• Si te diagnostican un problema GES, pide que te entreguen el *formulario de constancia GES*.\n"
        "• Si no se cumple el plazo, puedes reclamar en FONASA para que te asignen otro prestador.\n\n"
        "Revisa tu problema de salud en fonasa.cl → «GES».",
    ),
    "licencia": (
        "📝 Licencia médica",
        "📝 *Licencia médica*\n\n"
        "• Revisa el estado de tu licencia en *Mi FONASA* con tu ClaveÚnica.\n"
        "• Una vez *aprobada*, el pago se realiza en un plazo de *hasta 15 días*.\n"
        "• Si fue rechazada o reducida, puedes apelar dentro del plazo que indica la resolución.",
    ),
    "devolucion": (
        "💸 Devoluciones",
        "💸 *Devoluciones*\n\n"
        "1. Entra a *Mi FONASA* → «Devoluciones».\n"
        "2. Revisa si tienes montos a favor y sigue los pasos.\n"
        "3. El trámite puede tardar *hasta 30 días hábiles*.",
    ),
}

INFO = hospital.INFO
VISITAS = hospital.VISITAS
PREPARACION = hospital.PREPARACION
