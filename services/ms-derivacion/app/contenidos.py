"""Contenidos informativos de la Guía de Ruta, portados desde el prototipo
(legacy/services.py). Revisables por el equipo clínico sin tocar la lógica."""
# fmt: off

def interconsulta_instructions(ges_option):
    if ges_option == "Sí, es GES":
        return (
            "✅ *INTERCONSULTA GES (Garantías Explícitas en Salud)*\n\n"
            "📋 **¿Qué es?** Una derivación a especialista con cobertura garantizada por ley.\n\n"
            "📝 **Pasos a seguir:**\n"
            "1️⃣ Lleva tu interconsulta al *SOME del CESFAM* donde estás inscrito\n"
            "2️⃣ Solicita el *número de seguimiento GES* (muy importante)\n"
            "3️⃣ Te contactarán dentro de los plazos GES para coordinar:\n"
            "   • Cita con especialista\n"
            "   • Exámenes previos si se requieren\n"
            "   • Tratamiento garantizado\n\n"
            "⏰ **Plazos GES:** Varían según patología (desde 24h hasta 90 días)\n\n"
            "💡 **Tip:** Guarda tu número de seguimiento para consultar estado.\n\n"
            "¿Quieres configurar un recordatorio de *revisión de estado GES*?"
        )
    else:
        return (
            "ℹ️ *INTERCONSULTA NO GES o sin confirmar*\n\n"
            "📋 **¿Qué es?** Derivación a especialista sin cobertura GES específica.\n\n"
            "📝 **Pasos a seguir:**\n"
            "1️⃣ Lleva la interconsulta al *SOME del CESFAM* donde estás inscrito\n"
            "2️⃣ Confirma que quede *correctamente ingresada* en el sistema\n"
            "3️⃣ Pregunta si necesitas *exámenes previos* antes de la cita\n"
            "4️⃣ Solicita un *número de contacto* para hacer seguimiento\n"
            "5️⃣ Pregunta por los *tiempos de espera estimados*\n\n"
            "⚠️ **Importante:** Los tiempos pueden ser variables (no están garantizados como en GES)\n\n"
            "💡 **Tip:** Si tu condición empeora mientras esperas, consulta nuevamente.\n\n"
            "¿Te indico en qué sede del CESFAM hacer el trámite?"
        )

def exams_steps():
    return (
        "🧪 *ORDEN DE EXÁMENES / PROCEDIMIENTOS*\n\n"
        "📋 **¿Qué es?** Solicitud médica para realizar estudios diagnósticos.\n\n"
        "📝 **Pasos a seguir:**\n"
        "1️⃣ *Agenda tu hora:*\n"
        "   • En SOME del CESFAM (exámenes básicos)\n"
        "   • En laboratorio externo (si así se indica)\n"
        "   • Llamando al número que aparece en la orden\n\n"
        "2️⃣ *Antes de ir, verifica:*\n"
        "   • Si requiere *ayuno* (8-12 horas sin comer)\n"
        "   • Horarios de atención del laboratorio\n"
        "   • Si necesitas suspender algún medicamento\n\n"
        "3️⃣ *El día del examen lleva:*\n"
        "   • Cédula de identidad\n"
        "   • Orden médica original\n"
        "   • Credencial de salud (si tienes)\n\n"
        "4️⃣ *Después del examen:*\n"
        "   • Pregunta cuándo estarán los resultados\n"
        "   • Retira los resultados en la fecha indicada\n"
        "   • Agenda control con tu médico tratante\n\n"
        "💡 **Tip:** Algunos exámenes como glicemia, colesterol, triglicéridos requieren ayuno.\n\n"
        "¿Quieres que revisemos si tu examen requiere *ayuno*?"
    )

def urgent_referral_steps():
    return (
        "🚨 *DERIVACIÓN URGENTE*\n\n"
        "📋 **¿Qué es?** Referencia médica para atención inmediata en servicios de urgencia.\n\n"
        "⚠️ **ACCIÓN INMEDIATA REQUERIDA:**\n"
        "1️⃣ *Dirígete de inmediato* al servicio indicado:\n"
        "   • SAPU (Servicio de Atención Primaria de Urgencia)\n"
        "   • SAR (Servicio de Alta Resolución)\n"
        "   • Urgencia hospitalaria\n\n"
        "2️⃣ *Si tu estado empeora en el trayecto:*\n"
        "   • Llama al 131 (SAMU) inmediatamente\n"
        "   • No esperes, busca el centro de salud más cercano\n\n"
        "3️⃣ *Lleva contigo:*\n"
        "   • Cédula de identidad\n"
        "   • Derivación urgente (papel que te dieron)\n"
        "   • Medicamentos que tomas habitualmente\n"
        "   • Exámenes recientes (si los tienes)\n\n"
        "📞 **Números de emergencia:**\n"
        "   • SAMU: 131\n"
        "   • Bomberos: 132\n"
        "   • Carabineros: 133\n\n"
        "💡 **Importante:** En urgencias médicas reales, NO esperes respuesta del chatbot.\n\n"
        "¿Te indico el SAPU más cercano si me das tu comuna?"
    )

def req_docs_steps():
    return (
        "🧾 *CHECKLIST DE DOCUMENTOS Y REQUISITOS*\n\n"
        "📋 **Documentos básicos que siempre debes llevar:**\n\n"
        "🆔 **Obligatorios:**\n"
        "   • Cédula de identidad vigente\n"
        "   • Orden/interconsulta/receta original\n"
        "   • Credencial del sistema de salud (FONASA/ISAPRE)\n\n"
        "📄 **Documentos adicionales según el caso:**\n"
        "   • Exámenes previos relacionados (últimos 6 meses)\n"
        "   • Cartola del Registro Social de Hogares (para algunos trámites)\n"
        "   • Lista de medicamentos actuales\n"
        "   • Informes médicos anteriores\n"
        "   • Autorización del tutor (menores de edad)\n\n"
        "💡 **Tips importantes:**\n"
        "   • Siempre lleva originales Y fotocopias\n"
        "   • Si eres adulto mayor, puedes ir acompañado\n"
        "   • Anota preguntas que quieras hacer al profesional\n"
        "   • Llega 15 minutos antes de tu hora\n\n"
        "📱 **Recordatorio:** Puedes tomar foto de tus documentos como respaldo.\n\n"
        "¿Quieres que lo guarde y te envíe *recordatorios* personalizados?"
    )
