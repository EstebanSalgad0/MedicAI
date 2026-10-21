"""Respuestas propias del orquestador (no pertenecen a ningún microservicio de dominio)."""
from __future__ import annotations

import random

from medicai_common import hospital
from medicai_common.messages import DISCLAIMER, buttons, lst, text

# Pie legal permanente (WhatsApp admite hasta 60 caracteres en el pie)
FOOTER = "Sin diagnósticos ni recetas · Emergencias: SAMU 131"
MENU_OPTION = ("sys:menu", "🏠 Menú principal")


def menu(name: str | None = None, greet: bool = False, acting: dict | None = None, gestion: bool = False):
    saludo = ""
    if greet:
        nombre = f" {name.split()[0]}" if name else ""
        saludo = (f"👋 ¡Hola{nombre}! Soy *MedicAI*, el asistente digital del {hospital.NOMBRE} "
                  "y de los CESFAM del Maule. Soy un asistente automático, no una persona.\n\n")
    quien = f"👪 Estás gestionando los trámites de *{acting['name']}*.\n\n" if acting else ""
    cuidador = (("ate:cui:exit", "↩️ Volver a mi cuenta", f"Dejar de gestionar a {acting['name']}"[:72])
                if acting else ("ate:cui", "👪 Modo cuidador", "Trámites de un familiar a tu cargo"))
    return lst(
        saludo + quien + "¿En qué te puedo ayudar? Toca *Ver opciones* o escríbeme con tus palabras.",
        [
            ("agd:start", "📅 Agendar una hora", "Hospital Regional o tu CESFAM"),
            ("ori:start", "🩺 Tengo síntomas", "Te oriento sobre dónde consultar"),
            ("agd:mine", "🔁 Reprogramar mi hora", "Ver, cambiar o cancelar"),
            ("res:start", "📋 Resultados", "Estado de tus exámenes"),
            ("ate:fonasa", "💳 Trámites FONASA", "Bonos, GES, licencias, certificados"),
            ("rec:start", "💊 Medicamentos", "Recordatorios de tomas y recetas"),
            ("ori:animo", "🧠 Salud mental", "¿Cómo te has sentido?"),
            cuidador,
            ("ate:humano", "💬 Hablar con persona", "Mesa de ayuda del hospital"),
            ("sys:more", "➕ Más opciones", "Info, visitas, farmacia, gestión" if gestion else "Info, visitas, farmacia"),
        ],
        FOOTER,
        "Ver opciones",
    )


def more_menu(gestion: bool = False):
    opts = [
        ("ate:info", "🏥 Info del hospital", "Dirección, horarios, cómo llegar"),
        ("ate:visitas", "👥 Visitas", "Horarios y acompañantes"),
        ("ate:prep", "🧪 Preparar exámenes", "Ayuno y muestras"),
        ("med:start", "💊 Farmacia y retiros", "Stock y fechas de retiro"),
        ("rec:list", "⏰ Mis recordatorios", "Ver o eliminar"),
        ("der:start", "🧭 Guía de ruta", "Interconsultas, exámenes, recetas"),
        ("sys:help", "❓ ¿Cómo funciona?"),
    ]
    if gestion:
        opts.append(("sys:gestion", "📊 Modo gestión", "Indicadores del hospital"))
    opts.append(MENU_OPTION)
    return lst("➕ *Más opciones*", opts, FOOTER, "Ver opciones")


def gestion_menu():
    return lst(
        "📊 *Modo gestión*\n\nPregúntame por los indicadores con tus palabras, por ejemplo "
        "_¿cómo va el ausentismo?_ o _¿cuántas camas UCI quedan?_, o elige un tema:",
        [
            ("sys:ask:ausentismo", "📉 Ausentismo", "Inasistencia y horas recuperadas"),
            ("sys:ask:camas", "🛏️ Camas y UCI", "Ocupación por servicio"),
            ("sys:ask:urgencias", "🚑 Urgencias", "En espera y tiempo de espera"),
            ("sys:ask:listas", "⏳ Listas de espera", "Mediana y cumplimiento GES"),
            ("sys:ask:pabellones", "🔪 Pabellones", "Utilización y suspensiones"),
            ("sys:ask:chatbot", "🤖 Chatbot", "Resolución, temas y satisfacción"),
            MENU_OPTION,
        ],
        "Solo datos agregados, sin pacientes identificables",
        "Ver temas",
    )


def gestion_answer(answer: str):
    return buttons(answer[:1024], [("sys:gestion", "📊 Otra consulta"), MENU_OPTION], "Modo gestión • MedicAI")


def help_text():
    return text(
        "ℹ️ *Cómo usar MedicAI*\n\n"
        "Puedes tocar las opciones del menú o escribir con tus palabras, por ejemplo:\n"
        "• _quiero hora con el cardiólogo_\n"
        "• _me duele la garganta y tengo fiebre_\n"
        "• _¿están listos mis exámenes?_\n"
        "• _¿cómo saco el certificado de FONASA?_\n"
        "• _recuérdame tomar el losartán_\n\n"
        "Escribe *menú* para ver las opciones o *cancelar* para salir de un trámite.\n"
        "Soy un asistente automático: si necesitas a una persona, escribe *hablar con una persona*." + DISCLAIMER
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


def fallback(times: int, menu_msg):
    """1.º intento: pedir que lo diga de otra forma; 2.º: mostrar el menú; 3.º: ofrecer una persona."""
    if times >= 3:
        return [buttons("😕 Sigo sin entenderte, disculpa. ¿Quieres que te atienda una persona?",
                        [("ate:humano", "💬 Hablar con persona"), MENU_OPTION], FOOTER)]
    if times == 2:
        return [text("Puedo ayudarte con esto:"), menu_msg]
    return [text("🤔 No logré entenderte. ¿Me lo dices de otra forma o eliges una opción del menú?"), menu_msg]


def survey():
    return lst("⭐ *Ayúdanos a mejorar*\n¿Cómo evaluarías la atención que te di?",
               [("sys:survey:5", "😀 Excelente"), ("sys:survey:4", "🙂 Buena"), ("sys:survey:3", "😐 Regular"),
                ("sys:survey:2", "🙁 Mala"), ("sys:survey:1", "😞 Muy mala")], "Encuesta de satisfacción", "Evaluar")


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
    return text("🙏 ¡Gracias por tu evaluación! Nos ayuda a mejorar el servicio.")


def unsupported_media():
    return text("📎 Por ahora solo puedo leer mensajes de texto. ¿Me lo escribes, por favor?")
