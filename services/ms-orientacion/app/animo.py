"""Salud mental: chequeo breve de ánimo (0 a 3), contención y derivación.

No es terapia ni tamizaje clínico: es una puerta de entrada que acompaña y
ofrece agendar con salud mental. La ideación suicida la detecta antes el
detector de alarmas (tarjeta de emergencia + *4141).
"""
from __future__ import annotations

from medicai_common.contracts import DialogRequest, DialogResponse, DomainEvent, Handoff, reply
from medicai_common.messages import buttons, lst, text

FOOTER = "Salud mental • MedicAI"
ESCALA = [("0", "😞 Muy mal"), ("1", "🙁 Mal"), ("2", "😐 Más o menos"), ("3", "🙂 Bien")]
LINEAS = ("📞 Si en algún momento sientes que no puedes más o piensas en hacerte daño, llama al *\\*4141* "
          "(SaludableMente, gratuito, 24/7) o al *SAMU 131*.")
RESPIRACION = ("🌬️ *Respiración 4-4-6* (1 minuto)\n\n"
               "1. Inhala por la nariz contando hasta *4*.\n"
               "2. Mantén el aire contando hasta *4*.\n"
               "3. Bota el aire por la boca, lento, contando hasta *6*.\n\n"
               "Repítelo 5 veces. Ayuda a bajar la tensión del cuerpo.")


def ask_mood() -> DialogResponse:
    msg = lst("🧠 *¿Cómo te has sentido estos últimos días?*\n\nNo hay respuestas buenas ni malas. "
              "Lo que me cuentes queda entre nosotros y el equipo de salud.",
              [(f"ori:animo:{k}", v) for k, v in ESCALA], FOOTER, "Responder")
    return reply(msg, state={"step": "animo", "_menu": msg.model_dump()})


def result(score: int) -> DialogResponse:
    ev = DomainEvent(type="mood_check", props={"score": score})
    if score <= 1:
        body = ("💙 Gracias por contármelo. Lo que sientes es importante y no tienes que pasarlo solo/a.\n\n"
                "Hablar con un profesional puede ayudarte mucho. Puedo ayudarte a pedir una hora con el equipo de "
                f"salud mental.\n\n{LINEAS}")
        opts = [("ori:animo:agendar", "📅 Hora salud mental"), ("ori:animo:hablar", "💬 Seguir conversando")]
    else:
        body = (f"Gracias por contarme. Te propongo un ejercicio breve:\n\n{RESPIRACION}\n\n"
                "Si el malestar se mantiene, puedes pedir una hora con salud mental.")
        opts = [("ori:animo:agendar", "📅 Hora salud mental"), ("ori:animo:hablar", "💬 Seguir conversando")]
    return reply(buttons(body, opts, FOOTER), state=None, resolved=True, events=[ev])


def handle(req: DialogRequest, opt: str | None, state: dict) -> DialogResponse:
    arg = opt.split(":")[2] if opt and opt.count(":") >= 2 else ""
    if arg in ("0", "1", "2", "3"):
        return result(int(arg))
    if arg == "agendar":
        return reply(text("📅 Te ayudo a pedir la hora con salud mental en tu CESFAM, que es la puerta de entrada "
                          "a la atención psicológica en la red pública:"),
                     state=None, resolved=True,
                     handoff=Handoff(service="agendamiento", intent="agendar_cita",
                                     entities={"prestacion": "salud_mental"}))
    if arg == "hablar":
        return reply(text("Te leo. Cuéntame con tus palabras cómo te has sentido o qué te tiene así. ✍️"),
                     state={"step": "animo_hablar"})
    if state.get("step") == "animo_hablar" and req.text.strip():
        msg = buttons("💙 Gracias por confiar en mí. Lo que cuentas merece ser escuchado por alguien del equipo de "
                      "salud, que puede acompañarte de verdad. Yo soy un asistente automático y no reemplazo esa ayuda."
                      f"\n\n{LINEAS}",
                      [("ori:animo:agendar", "📅 Hora salud mental"), ("ate:humano:saludmental", "💬 Hablar con persona")],
                      FOOTER)
        return reply(msg, state=None, resolved=True, events=[DomainEvent(type="mood_talk")])
    return ask_mood()
