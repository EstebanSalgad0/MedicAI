"""Respuestas propias del orquestador (no pertenecen a ningún microservicio de dominio)."""
from __future__ import annotations

import random

from medicai_common.messages import DISCLAIMER, buttons, lst, text

FOOTER = "MedicAI • Tu asistente de salud"


def menu(name: str | None = None, greet: bool = False):
    saludo = f"👋 ¡Hola{' ' + name.split()[0] if name else ''}! Soy *MedicAI*, el asistente de tu CESFAM.\n\n" if greet else ""
    return lst(
        saludo + "¿En qué te puedo ayudar? Toca *Ver opciones* o escríbeme con tus palabras.",
        [
            ("agd:start", "🗓️ Agendar hora", "Reserva en tu CESFAM"),
            ("agd:mine", "📋 Mis horas", "Ver, reagendar o cancelar"),
            ("rec:start", "⏰ Recordar medicamentos", "Avisos para tus tomas"),
            ("rec:list", "💊 Mis recordatorios", "Ver o eliminar"),
            ("ori:start", "🩺 Orientación", "Dónde y cuándo consultar"),
            ("der:start", "🏥 Guía de ruta", "Interconsultas, exámenes, recetas"),
            ("med:start", "💊 Farmacia y retiros", "Stock y fechas de retiro"),
            ("sys:help", "❓ ¿Cómo funciona?"),
        ],
        FOOTER,
        "Ver opciones",
    )


def help_text():
    return text(
        "ℹ️ *Cómo usar MedicAI*\n\n"
        "Puedes tocar las opciones del menú o escribir con tus palabras, por ejemplo:\n"
        "• _quiero hora con la matrona_\n"
        "• _recuérdame tomar el losartán_\n"
        "• _me duele la garganta y tengo fiebre_\n"
        "• _me dieron una interconsulta_\n"
        "• _¿hay metformina en el CESFAM?_\n\n"
        "Escribe *menú* para ver las opciones o *cancelar* para salir de un trámite.\n"
        "🚨 En una emergencia llama al *131*." + DISCLAIMER
    )


def thanks(name: str | None):
    return text(random.choice([
        "¡De nada! 💙 Aquí estoy cuando me necesites.",
        f"Un gusto ayudarte{', ' + name.split()[0] if name else ''}. ¡Cuídate!",
        "Para eso estoy. Escribe *menú* si necesitas algo más. 😊",
    ]))


def bye(name: str | None):
    return text(f"👋 ¡Hasta pronto{', ' + name.split()[0] if name else ''}! Cuídate mucho." + DISCLAIMER)


def cancelled():
    return text("👍 Listo, dejé ese trámite. Escribe *menú* cuando quieras.")


def fallback(times: int):
    if times >= 2:
        return [text("😕 Sigo sin entenderte, disculpa. Si prefieres hablar con una persona:\n"
                     "📞 *Salud Responde: 600 360 7777* (24 h)\n"
                     "🏥 O acércate al *SOME* de tu CESFAM."), menu()]
    return [text("🤔 No logré entenderte. ¿Me lo dices de otra forma o eliges una opción?"), menu()]


def survey():
    return lst("⭐ *Ayúdanos a mejorar*\n¿Cómo evaluarías la atención que te di?",
               [("sys:survey:5", "😀 Excelente"), ("sys:survey:4", "🙂 Buena"), ("sys:survey:3", "😐 Regular"),
                ("sys:survey:2", "🙁 Mala"), ("sys:survey:1", "😞 Muy mala")], "Encuesta de satisfacción", "Evaluar")


MENU_OPTION = ("sys:menu", "🏠 Menú principal")


def with_menu_button(messages: list) -> list:
    """Al terminar un trámite, deja a mano la opción de volver al menú principal.

    - Último mensaje de texto: pasa a ser un mensaje con el botón de menú.
    - Último mensaje con menos de 3 botones: se le suma el botón.
    - Listas (menú, encuesta) o 3 botones: ya ofrecen opciones, no se tocan.
    """
    if not messages:
        return messages
    last = messages[-1]
    if any(o.id.startswith("sys:menu") for o in last.options):
        return messages
    if last.options:
        if last.type == "buttons" and len(last.options) < 3:
            ids = [o.id for o in last.options] + [MENU_OPTION[0]]
            titles = [o.title for o in last.options] + [MENU_OPTION[1]]
            messages[-1] = buttons(last.text, list(zip(ids, titles)), last.footer)
        return messages
    if len(last.text) <= 1024:  # límite del cuerpo de un mensaje interactivo de WhatsApp
        messages[-1] = buttons(last.text, [MENU_OPTION], last.footer)
    else:
        messages.append(buttons("¿Te ayudo con algo más?", [MENU_OPTION], FOOTER))
    return messages


def stale_option():
    return buttons("⌛ Esa opción ya no está vigente: el trámite terminó o pasó mucho tiempo. "
                   "¿Empezamos de nuevo?", [MENU_OPTION], FOOTER)


def survey_thanks():
    return text("🙏 ¡Gracias por tu evaluación! Nos ayuda a mejorar el servicio de tu CESFAM.")


def unsupported_media():
    return text("📎 Por ahora solo puedo leer mensajes de texto. ¿Me lo escribes, por favor?")
