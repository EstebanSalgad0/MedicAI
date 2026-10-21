"""Reglas clínicas de orientación por categoría.

Portadas sin cambios de contenido desde el prototipo monolítico (legacy/services.py),
donde fueron validadas con profesionales de enfermería, obstetricia y
puericultura. Se mantienen deterministas y auditables a propósito: en salud,
cada salida debe poder explicarse (principios OMS 2021 y AI Act, IA de alto
riesgo). La IA generativa NO decide la orientación clínica.
"""
# flake8: noqa
# fmt: off

EJEMPLOS_SINTOMAS = {
    "respiratorio":    "tos seca, fiebre alta, dificultad para respirar",
    "bucal":           "dolor punzante en muela, sensibilidad al frío, sangrado de encías",
    "infeccioso":      "ardor al orinar, fiebre, orina frecuente",
    "cardiovascular":  "dolor en el pecho al esfuerzo, palpitaciones, mareos",
    "metabolico":      "sed excesiva, orina frecuentemente, pérdida de peso",
    "neurologico":     "dolor de cabeza pulsátil, náuseas, fotofobia",
    "musculoesqueletico": "dolor en espalda baja al levantarte, rigidez",
    "saludmental":     "ansiedad constante, insomnio, aislamiento social",
    "dermatologico":   "granos en cara, picazón intensa, enrojecimiento",
    "otorrinolaringologico": "ojos rojos, picazón ocular, secreción",
    "ginecologico":    "dolor pélvico durante menstruación, flujo anormal",
    "digestivo":       "diarrea, dolor abdominal inferior, gases"
}

RECOMENDACIONES_GENERALES = {
    "respiratorio": (
        "• Mantén reposo y buena hidratación.\n"
        "• Humidifica el ambiente y ventílalo a diario.\n"
        "• Usa mascarilla si convives con personas de riesgo.\n"
        "• Evita irritantes como humo, polvo o polución.\n"
        "• Controla tu temperatura cada 6 h.\n"
        "Si empeoras o la fiebre supera 39 °C, consulta a un profesional."
    ),
    "bucal": (
        "• Cepíllate los dientes al menos dos veces al día.\n"
        "• Usa hilo dental y enjuagues antisépticos.\n"
        "• Evita alimentos muy ácidos, azúcares o demasiado fríos/calientes.\n"
        "• Controla sangrados o mal aliento persistente.\n"
        "• Programa limpieza dental profesional anualmente.\n"
        "Si el dolor o sangrado continúa, visita a tu odontólogo."
    ),
    "infeccioso": (
        "• Guarda reposo e hidrátate con frecuencia.\n"
        "• Lávate las manos y desinfecta superficies de alto contacto.\n"
        "• Aísla si tu patología puede contagiar (fiebre, erupciones).\n"
        "• Usa mascarilla para no infectar a otros.\n"
        "• Observa tu temperatura y forúnculos si los hubiera.\n"
        "Si persiste la fiebre o hay sangre en secreciones, acude al médico."
    ),
    "cardiovascular": (
        "• Controla tu presión arterial regularmente.\n"
        "• Sigue una dieta baja en sal y grasas saturadas.\n"
        "• Realiza ejercicio moderado (30 min diarios) si tu médico lo autoriza.\n"
        "• Evita tabaco y consumo excesivo de alcohol.\n"
        "• Vigila dolores torácicos, palpitaciones o hinchazón.\n"
        "Si aparece dolor en el pecho o disnea, busca ayuda inmediata."
    ),
    "metabolico": (
        "• Mantén dieta equilibrada y controla los carbohidratos.\n"
        "• Realiza actividad física regular (mín. 150 min/semana).\n"
        "• Mide glucosa/lípidos según pauta médica.\n"
        "• Toma la medicación tal como te la recetaron.\n"
        "• Evita azúcares refinados y grasas trans.\n"
        "Si notas hipoglucemia (sudor, temblores) o hiperglucemia grave, consulta hoy."
    ),
    "neurologico": (
        "• Descansa en ambientes oscuros y silenciosos.\n"
        "• Identifica desencadenantes (estrés, luces, ruido).\n"
        "• Practica técnicas de respiración o relajación.\n"
        "• Lleva un diario de frecuencia y severidad de tus síntomas.\n"
        "• Mantente bien hidratado.\n"
        "Si aparecen déficit neurológicos (desorientación, debilidad), acude al neurólogo."
    ),
    "musculoesqueletico": (
        "• Aplica frío o calor local según indicación.\n"
        "• Realiza estiramientos suaves y evita movimientos bruscos.\n"
        "• Mantén reposo relativo, sin inmovilizar en exceso.\n"
        "• Considera fisioterapia o kinesiterapia.\n"
        "• Analgésicos de venta libre según prospecto.\n"
        "Si el dolor impide tu marcha o persiste más de 72 h, consulta al traumatólogo."
    ),
    "saludmental": (
        "• Practica respiración diafragmática y mindfulness.\n"
        "• Mantén rutina de sueño regular.\n"
        "• Realiza actividad física o caminatas diarias.\n"
        "• Comparte con tu red de apoyo (familia/amigos).\n"
        "• Considera terapia psicológica si los síntomas persisten.\n"
        "Si hay riesgo de daño a ti o a otros, busca ayuda de urgencia."
    ),
    "dermatologico": (
        "• Hidrata la piel con emolientes adecuados.\n"
        "• Evita jabones o detergentes agresivos.\n"
        "• No rasques lesiones ni uses remedios caseros.\n"
        "• Protege tu piel del sol con FPS ≥ 30.\n"
        "• Identifica y evita alérgenos o irritantes.\n"
        "Si notas pus, fiebre o expansión de la lesión, consulta a dermatología."
    ),
    "otorrinolaringologico": (
        "• Realiza lavados nasales y oculares con solución salina.\n"
        "• Evita rascarte o hurgarte en oído y nariz.\n"
        "• Controla exposición a alérgenos (polvo, pólenes).\n"
        "• No automediques antibióticos; sigue prescripción.\n"
        "• Descansa la voz y evita ambientes ruidosos.\n"
        "Si hay dolor intenso, secreción purulenta o pérdida auditiva, acude al ORL."
    ),
    "ginecologico": (
        "• Mantén higiene íntima con productos suaves.\n"
        "• Usa ropa interior de algodón y cambia con frecuencia.\n"
        "• Controla cualquier flujo anormal o sangrado intenso.\n"
        "• Alivia dolor menstrual con calor local y analgésicos según prospecto.\n"
        "• Programa chequeos ginecológicos anuales.\n"
        "Si hay fiebre, dolor severo o sangrado fuera de ciclo, busca atención médica."
    ),
    "digestivo": (
        "• Sigue dieta rica en fibra (frutas, verduras, cereales integrales).\n"
        "• Hidrátate agua o soluciones de rehidratación oral.\n"
        "• Evita comidas muy grasas, picantes o irritantes.\n"
        "• Come despacio y mastica bien.\n"
        "• Controla gases con caminatas suaves.\n"
        "Si observas sangre en heces o dolor abdominal muy intenso, consulta urgente."
    ),
    "default": (
        "• Mantén reposo e hidratación.\n"
        "• Observa tus síntomas a diario.\n"
        "• Consulta a un profesional si empeoras."
    ),
}

SINTOMAS_CONOCIDOS = {
    "respiratorio": [
        "tos leve", "tos seca", "tos persistente", "tos",
        "fiebre", "fiebre alta", "estornudos", "congestion nasal", "congestión nasal",
        "dolor de garganta", "dolor al tragar", "garganta inflamada",
        "cansancio", "dolores musculares", "dolor en el pecho", "pecho apretado",
        "flema", "silbidos", "picazón", "picazon", "pérdida de olfato",
        "opresión torácica", "opresion toracica"
    ],
    "bucal": [
        "dolor punzante", "sensibilidad",
        "encías inflamadas", "encías retraídas",
        "sangrado", "mal aliento",
        "llagas", "pequeñas", "dolorosas",
        "dolor al masticar", "tensión mandibular",
        "movilidad", "dolor mandibular", "rechinar"
    ],
    "infeccioso": [
        "ardor al orinar", "fiebre", "orina frecuente",
        "diarrea", "vómitos", "dolor abdominal",
        "manchas", "picazón", "picazon", "ictericia"
    ],
    "cardiovascular": [
        "dolor en el pecho", "palpitaciones", "cansancio", "mareos",
        "falta de aire", "hinchazón", "hinchazon", "sudor frío", "sudor frio",
        "náuseas", "presión", "presion",
        "dolor al caminar", "desaparece", "brazo izquierdo"
    ],
    "metabolico": [
        "sed excesiva", "orina frecuentemente", "pérdida de peso", "aumento de peso",
        "cansancio", "visión borrosa", "vision borrosa", "colesterol", "antecedentes",
        "nerviosismo", "sudoración", "sudoracion", "circunferencia abdominal",
        "sobrepeso", "piel seca", "intolerancia al frio", "intolerancia al frío"
    ],
    "neurologico": [
        "dolor de cabeza", "pulsatil", "pulsátil", "náuseas", "nauseas",
        "fotofobia", "estrés", "estres", "tensión", "tension",
        "temblores", "lentitud", "rigidez", "sacudidas", "desmayo",
        "confusión", "confusion", "pérdida de memoria", "perdida de memoria",
        "desorientación", "desorientacion",
        "hormigueo", "fatiga", "dolor facial", "punzante"
    ],
    "musculoesqueletico": [
        "dolor en espalda baja", "dolor articular", "inflamación",
        "rigidez", "dolor muscular", "fatiga", "torcedura", "bursa"
    ],
    "saludmental": [
        "ansiedad", "dificultad para relajarse", "tristeza persistente",
        "pérdida de interés", "fatiga", "cambios extremos", "hiperactividad",
        "ataques de pánico", "miedo a morir", "flashbacks", "hipervigilancia",
        "compulsiones", "pensamientos repetitivos"
    ],
    "dermatologico": [
        "granos", "picazón", "picazon", "erupción", "erupcion",
        "escamas", "engrosadas", "ampolla", "ronchas", "aparecen",
        "lesión redonda", "lesion redonda", "borde rojo", "bultos", "duros"
    ],
    "otorrinolaringologico": [
        "ojos rojos", "picazón", "picazon", "secreción", "secrecion",
        "dolor de oído", "dolor de oido", "fiebre", "tapado",
        "presion en cara", "presión en cara", "secrecion nasal espesa",
        "zumbido", "visión borrosa", "vision borrosa", "halos",
        "dificultad para ver", "vision nublada", "visión nublada"
    ],
    "ginecologico": [
        "dolor al orinar", "orina turbia", "turbia", "fiebre",
        "flujo anormal", "picazón", "picazon", "ardor",
        "dolor pélvico", "dolor pelvico", "menstruación dolorosa",
        "menstruacion dolorosa", "sangrado menstrual",
        "irritabilidad", "dolor mamario", "cambios premenstruales",
        "dolor testicular", "perineal"
    ],
    "digestivo": [
        "acidez", "ardor", "comer", "aliment", "diarrea",
        "estreñimiento", "evacuaciones difíciles", "evacuaciones dificiles",
        "dolor abdominal", "dolor al evacuar", "gases", "hinchazón",
        "hinchazon", "sangrado", "lacteos", "lácteos"
    ],
}

def diagnostico_respiratorio(respuestas):
    respuestas = respuestas.lower()
    if (
        "tos leve" in respuestas
        and "estornudos" in respuestas
        and "congestion nasal" in respuestas
    ):
        return (
            "Resfriado común",
            "Autocuidado en casa",
            "Mantén reposo e hidratación, aprovecha líquidos calientes y, si tienes congestión, usa solución salina nasal. Usa mascarilla si estás con personas de riesgo."
        )
    elif (
        "tos seca" in respuestas
        and "fiebre" in respuestas
        and "dolores musculares" in respuestas
    ):
        return (
            "Gripe (influenza)",
            "Autocuidado + control",
            "Reposa, mantén una buena hidratación y utiliza paracetamol o ibuprofeno según prospecto. Controla tu temperatura cada 6 h."
        )
    elif (
        "dolor al tragar" in respuestas
        and "fiebre" in respuestas
        and "garganta inflamada" in respuestas
    ):
        return (
            "Faringitis / Amigdalitis / Laringitis",
            "Requiere atención si persiste",
            "Haz gárgaras con agua tibia y sal, hidratación abundante. Si el dolor dura más de 48 h o hay placas en la garganta, consulta al médico para posible tratamiento antibiótico."
        )
    elif (
        "tos persistente" in respuestas
        and "flema" in respuestas
        and "pecho apretado" in respuestas
    ):
        return (
            "Bronquitis",
            "Medir gravedad",
            "Evita irritantes (humo, polvo), mantente hidratado y usa expectorantes de venta libre. Si empeora la dificultad para respirar o la fiebre persiste, acude al médico."
        )
    elif (
        "fiebre alta" in respuestas
        and "dificultad respiratoria" in respuestas
    ):
        return (
            "Neumonía",
            "Urgencia médica",
            "Esta combinación sugiere neumonía: acude de inmediato a un servicio de urgencias u hospital."
        )
    elif (
        "opresión torácica" in respuestas
        and "silbidos" in respuestas
    ):
        return (
            "Asma",
            "Evaluar crisis",
            "Si tienes salbutamol, úsalo según indicaciones. Si no mejora en 15 min o empeora la respiración, llama al 131 o acude a urgencias."
        )
    elif (
        "estornudos" in respuestas
        and "congestión nasal" in respuestas
        and "picazón" in respuestas
    ):
        return (
            "Rinitis alérgica",
            "Tratamiento ambulatorio",
            "Evita alérgenos (polvo, pólenes), antihistamínicos orales y lavados nasales con solución salina. Consulta a tu alergólogo si persiste."
        )
    elif (
        "tos seca" in respuestas
        and "fiebre" in respuestas
        and "pérdida de olfato" in respuestas
    ):
        return (
            "COVID-19",
            "Sospecha, test y aislamiento",
            "Aíslate y haz prueba PCR lo antes posible. Monitorea tus síntomas cada día y consulta si aparece dificultad respiratoria."
        )
    else:
        return None, None, None


def diagnostico_bucal(respuestas):
    respuestas = respuestas.lower()
    if (
        "dolor punzante" in respuestas
        and "sensibilidad" in respuestas
    ):
        return (
            "Caries",
            "Requiere atención odontológica",
            "Mantén una higiene bucal rigurosa (cepillado y uso de hilo dental), evita alimentos muy ácidos o muy fríos/calientes y consulta a un odontólogo para tratar la cavidad."
        )
    elif (
        "encías inflamadas" in respuestas
        and "sangrado" in respuestas
        and "mal aliento" in respuestas
    ):
        return (
            "Gingivitis",
            "Higiene mejorada + control",
            "Mejora tu higiene bucal con cepillado suave dos veces al día, uso de hilo dental y enjuagues antisépticos. Si los síntomas persisten tras una semana, visita a tu dentista."
        )
    elif (
        "encías retraídas" in respuestas
        and "dolor al masticar" in respuestas
        and "movilidad" in respuestas
    ):
        return (
            "Periodontitis",
            "Atención odontológica urgente",
            "Acude al odontólogo de inmediato; podrías necesitar raspado y alisado radicular para frenar la pérdida de tejido periodontal."
        )
    elif (
        "llagas" in respuestas
        and "pequeñas" in respuestas
        and "dolorosas" in respuestas
    ):
        return (
            "Aftas bucales",
            "Manejo local + observar",
            "Evita alimentos ácidos o picantes, enjuaga con agua tibia y sal, y utiliza gel o crema tópica para aliviar el dolor. Si duran más de 2 semanas, consulta a tu dentista."
        )
    elif (
        "dolor mandibular" in respuestas
        and "tensión" in respuestas
        and "rechinar" in respuestas
    ):
        return (
            "Bruxismo",
            "Uso de férula / evaluación",
            "Considera usar una férula de descarga nocturna, técnicas de relajación y fisioterapia mandibular. Evalúa con un odontólogo o especialista en ATM."
        )
    else:
        return None, None, None


def diagnostico_infeccioso(respuestas):
    respuestas = respuestas.lower()
    if (
        "ardor al orinar" in respuestas
        and "fiebre" in respuestas
        and "orina frecuente" in respuestas
    ):
        return (
            "Infección urinaria",
            "Atención médica no urgente",
            "Hidrátate abundantemente, evita irritantes (café, alcohol) y consulta al médico si persiste o hay sangre en la orina."
        )
    elif (
        "diarrea" in respuestas
        and "vómitos" in respuestas
        and "dolor abdominal" in respuestas
    ):
        return (
            "Gastroenteritis",
            "Hidratación + reposo",
            "Mantén reposo, usa soluciones de rehidratación oral y observa si hay signos de deshidratación. Acude al médico si empeora."
        )
    elif (
        "dolor estomacal persistente" in respuestas
        and "náuseas" in respuestas
    ):
        return (
            "Infección por Helicobacter pylori",
            "Evaluación médica necesaria",
            "Solicita pruebas de H. pylori y consulta con tu médico para iniciar tratamiento antibiótico y protector gástrico."
        )
    elif (
        "fiebre" in respuestas
        and "erupción" in respuestas
        and "ampollas" in respuestas
    ):
        return (
            "Varicela",
            "Reposo + aislamiento",
            "Mantén reposo, controla la fiebre con paracetamol y evita rascarte. Aísla hasta que todas las ampollas se sequen."
        )
    elif (
        "manchas rojas" in respuestas
        and "tos" in respuestas
        and "conjuntivitis" in respuestas
    ):
        return (
            "Sarampión",
            "Evaluación médica urgente",
            "Acude de inmediato al médico, confirma tu estado de vacunación y evita el contacto con personas susceptibles."
        )
    elif (
        "erupción leve" in respuestas
        and "inflamación ganglionar" in respuestas
    ):
        return (
            "Rubéola",
            "Observación + test",
            "Realiza prueba de rubéola y evita el contacto con embarazadas. Sigue las indicaciones de tu médico."
        )
    elif (
        "dolor en mejillas" in respuestas
        and "fiebre" in respuestas
    ):
        return (
            "Paperas",
            "Cuidado en casa + control",
            "Aplica calor suave en la zona, toma analgésicos según indicación y descansa. Consulta si hay complicaciones."
        )
    elif (
        "cansancio" in respuestas
        and "piel amarilla" in respuestas
        and "fiebre" in respuestas
    ):
        return (
            "Hepatitis A/B/C",
            "Evaluación inmediata y pruebas de laboratorio",
            "Solicita pruebas de función hepática y marcadores virales. Acude al médico cuanto antes."
        )
    else:
        return None, None, None


def diagnostico_cardiovascular(respuestas):
    respuestas = respuestas.lower()
    if (("presion" in respuestas or "presión" in respuestas)
        and ("sin síntomas" in respuestas or "alta" in respuestas)):
        return (
            "Hipertensión arterial",
            "Control ambulatorio",
            "Controla tu presión arterial regularmente, lleva una dieta baja en sal, haz ejercicio moderado y sigue las indicaciones de tu médico."
        )
    elif ("cansancio" in respuestas
          and "falta de aire" in respuestas
          and "hinchaz" in respuestas):
        return (
            "Insuficiencia cardíaca",
            "Evaluación clínica pronta",
            "Monitorea tu peso y la hinchazón, reduce la ingesta de líquidos si está indicado y consulta a un cardiólogo lo antes posible."
        )
    elif "palpitaciones" in respuestas:
        return (
            "Arritmias",
            "Requiere electrocardiograma",
            "Agenda un electrocardiograma y consulta con un especialista en cardiología para evaluar tu ritmo cardíaco."
        )
    elif ("dolor en el pecho" in respuestas
          and "brazo izquierdo" in respuestas
          and ("sudor frio" in respuestas or "sudor frío" in respuestas)):
        return (
            "Infarto agudo al miocardio",
            "Urgencia médica inmediata",
            "Llama a emergencias (SAMU 131) de inmediato o acude al hospital más cercano. No esperes."
        )
    elif ("dolor al caminar" in respuestas
          and "desaparece" in respuestas):
        return (
            "Aterosclerosis (angina)",
            "Evaluación médica en menos de 24 hrs",
            "Evita esfuerzos intensos hasta la valoración, y consulta con un cardiólogo para pruebas de perfusión o angiografía."
        )
    else:
        return None, None, None


def diagnostico_metabolico(respuestas):
    respuestas = respuestas.lower()
    if ("sed excesiva" in respuestas
        and "orina frecuentemente" in respuestas
        and "pérdida de peso" in respuestas):
        return (
            "Diabetes tipo 1",
            "Evaluación médica urgente",
            "Acude a un centro de salud para medición de glucosa en sangre y valoración endocrinológica inmediata."
        )
    elif ("cansancio" in respuestas
          and "visión borrosa" in respuestas
          and "sobrepeso" in respuestas):
        return (
            "Diabetes tipo 2",
            "Control y exámenes de laboratorio",
            "Realiza un hemograma de glucosa y HbA1c, ajusta dieta y actividad física, y programa consulta con endocrinología."
        )
    elif ("piel seca" in respuestas
          and ("intolerancia al frio" in respuestas or "frío" in respuestas)):
        return (
            "Hipotiroidismo",
            "Control endocrinológico",
            "Solicita perfil de tiroides (TSH, T4) y ajusta tu tratamiento si ya estás en seguimiento."
        )
    elif (("nerviosismo" in respuestas
           and ("sudoracion" in respuestas or "sudoración" in respuestas))
          and "pérdida de peso" in respuestas):
        return (
            "Hipertiroidismo",
            "Evaluación clínica y TSH",
            "Pide análisis de tiroides y consulta con endocrinólogo para manejo con antitiroideos o terapia con yodo."
        )
    elif ("circunferencia abdominal" in respuestas
          and ("presion alta" in respuestas or "presión alta" in respuestas)):
        return (
            "Síndrome metabólico",
            "Evaluación de riesgo cardiovascular",
            "Controla tu peso, presión y lípidos. Programa un chequeo cardiovascular completo."
        )
    elif "colesterol" in respuestas and "antecedentes" in respuestas:
        return (
            "Colesterol alto",
            "Prevención + examen de perfil lipídico",
            "Realiza un perfil de lípidos, ajusta dieta baja en grasas saturadas y considera estatinas si lo indica tu médico."
        )
    elif "dolor en la articulación" in respuestas and "dedo gordo" in respuestas:
        return (
            "Gota",
            "Evaluación médica ambulatoria",
            "Confirma con ácido úrico en sangre, modera el consumo de purinas y consulta con reumatología."
        )
    else:
        return None, None, None


def diagnostico_neurologico(respuestas):
    respuestas = respuestas.lower()
    if ("dolor de cabeza" in respuestas
        and ("pulsatil" in respuestas or "pulsátil" in respuestas)
        and ("nauseas" in respuestas or "náuseas" in respuestas)
        and "fotofobia" in respuestas):
        return (
            "Migraña",
            "Manejo con analgésicos + control",
            "Descansa en ambiente oscuro, utiliza triptanes o analgésicos según prescripción y lleva un diario de desencadenantes."
        )
    elif ("dolor de cabeza" in respuestas
          and "estrés" in respuestas):
        return (
            "Cefalea tensional",
            "Autocuidado + relajación",
            "Aplica compresas frías o calientes, practica técnicas de relajación y corrige postura."
        )
    elif ("sacudidas" in respuestas
          and "desmayo" in respuestas
          and ("confusion" in respuestas or "confusión" in respuestas)):
        return (
            "Epilepsia",  
            "Evaluación neurológica urgente",
            "Registra los episodios y consulta con neurología para EEG y ajuste de medicación anticonvulsivante."
        )
    elif ("temblores" in respuestas
          and "lentitud" in respuestas
          and "rigidez" in respuestas):
        return (
            "Parkinson",
            "Evaluación neurológica",
            "Agrega fisioterapia y consulta con neurología para iniciar tratamiento con levodopa o agonistas."
        )
    elif (("perdida de memoria" in respuestas or "pérdida de memoria" in respuestas)
          and "desorientación" in respuestas):
        return (
            "Alzheimer",
            "Evaluación por especialista",
            "Realiza pruebas cognitivas y consulta con neurología o geriatría para manejo multidisciplinario."
        )
    elif ("fatiga" in respuestas
          and "hormigueos" in respuestas
          and ("vision borrosa" in respuestas or "visión borrosa" in respuestas)):
        return (
            "Esclerosis múltiple",
            "Derivación neurológica",
            "Consulta con neurología para RMN cerebral y lumbar y comenzar terapia modificadora de enfermedad."
        )
    elif ("dolor facial" in respuestas
          and "punzante" in respuestas):
        return (
            "Neuralgia del trigémino",
            "Tratamiento farmacológico",
            "Inicia carbamazepina o gabapentina según indicación médica y valora bloqueo del nervio si persiste."
        )
    else:
        return None, None, None

def diagnostico_musculoesqueletico(respuestas):
    respuestas = respuestas.lower()
    if (
        "dolor en espalda baja" in respuestas
        and "sin golpe" in respuestas
    ):
        return (
            "Lumbalgia",
            "Reposo + fisioterapia",
            "Aplica calor local, evita levantar pesos y realiza estiramientos suaves con guía de kinesiología."
        )
    elif (
        "dolor articular" in respuestas
        and ("inflamacion" in respuestas or "inflamación" in respuestas)
        and "rigidez" in respuestas
    ):
        return (
            "Artritis",
            "Evaluación médica reumatológica",
            "Solicita marcadores inflamatorios (VSG, PCR) y consulta con reumatología para manejo con AINEs o DMARDs."
        )
    elif (
        "dolor articular" in respuestas
        and "uso" in respuestas
        and ("sin inflamacion" in respuestas or "sin inflamación" in respuestas)
    ):
        return (
            "Artrosis",
            "Ejercicio suave + control",
            "Refuerza musculatura con ejercicios de bajo impacto y considera condroprotectores si lo indica tu médico."
        )
    elif (
        "dolor muscular generalizado" in respuestas
        and "fatiga" in respuestas
    ):
        return (
            "Fibromialgia",
            "Manejo crónico integral",
            "Combina ejercicio aeróbico suave, terapia cognitivo‑conductual y manejo del dolor con tu médico."
        )
    elif (
        "dolor al mover" in respuestas
        and "sobreuso" in respuestas
    ):
        return (
            "Tendinitis",
            "Reposo local + analgésicos",
            "Aplica hielo, inmoviliza la zona en reposo y toma AINEs según indicación médica."
        )
    elif (
        "dolor localizado" in respuestas
        and "bursa" in respuestas
    ):
        return (
            "Bursitis",
            "Reposo + hielo + evaluación",
            "Aplica frío local y consulta con ortopedia o fisiatría si persiste para posible infiltración."
        )
    elif "torcedura" in respuestas:
        return (
            "Esguince",
            "Reposo, hielo, compresión, elevación (RICE)",
            "Sujeta con venda elástica, eleva la zona y reevalúa en 48 h con un profesional."
        )
    else:
        return None, None, None


def diagnostico_salud_mental(respuestas):
    respuestas = respuestas.lower()
    if (
        "ansiedad" in respuestas
        and "dificultad para relajarse" in respuestas
    ):
        return (
            "Ansiedad generalizada",
            "Apoyo psicoemocional + técnicas de autorregulación",
            "Práctica respiración diafragmática, mindfulness y considera terapia cognitivo‑conductual."
        )
    elif (
        "tristeza persistente" in respuestas
        and "pérdida de interés" in respuestas
        and "fatiga" in respuestas
    ):
        return (
            "Depresión",
            "Apoyo clínico + evaluación emocional",
            "Consulta con psiquiatría o psicología para evaluar terapia y, si es necesario, antidepresivos."
        )
    elif (
        "cambios extremos" in respuestas
        and "hiperactividad" in respuestas
    ):
        return (
            "Trastorno bipolar",
            "Evaluación profesional integral",
            "Valora estabilizadores del ánimo con psiquiatría y seguimiento estrecho."
        )
    elif (
        "ataques de pánico" in respuestas
        and "miedo a morir" in respuestas
    ):
        return (
            "Trastorno de pánico",
            "Manejo con técnicas de respiración + orientación",
            "Aprende respiración controlada y considera ISRS o benzodiacepinas en pauta corta."
        )
    elif (
        "flashbacks" in respuestas
        and "hipervigilancia" in respuestas
    ):
        return (
            "TEPT",
            "Acompañamiento psicológico",
            "Terapia de exposición y EMDR con psicólogo especializado."
        )
    elif (
        "compulsiones" in respuestas
        or "pensamientos repetitivos" in respuestas
    ):
        return (
            "TOC",
            "Detección temprana + derivación especializada",
            "Terapia cognitivo‑conductual con ERP y, si hace falta, ISRS a dosis altas."
        )
    else:
        return None, None, None


def diagnostico_dermatologico(respuestas):
    respuestas = respuestas.lower()
    if (
        "granos" in respuestas
        and ("cara" in respuestas or "pecho" in respuestas or "espalda" in respuestas)
    ):
        return (
            "Acné",
            "Manejo domiciliario + higiene",
            "Limpia con jabón suave, evita productos comedogénicos y consulta dermatología si persiste."
        )
    elif (
        "piel seca" in respuestas
        and "enrojecida" in respuestas
        and ("picazon" in respuestas or "picazón" in respuestas)
    ):
        return (
            "Dermatitis atópica",
            "Hidratación + evitar alérgenos",
            "Emuslivos frecuentes, evita jabones agresivos y considera corticoides tópicos si lo indica tu médico."
        )
    elif (
        "placas rojas" in respuestas
        and "escamas" in respuestas
        and "engrosadas" in respuestas
    ):
        return (
            "Psoriasis",
            "Evaluación dermatológica",
            "Consulta dermatológica para valorar calcipotriol o fototerapia."
        )
    elif (
        "ronchas" in respuestas
        and "aparecen" in respuestas
        and ("rapido" in respuestas or "rápido" in respuestas)
    ):
        return (
            "Urticaria",
            "Posible alergia / estrés",
            "Antihistamínicos orales y evita desencadenantes identificados."
        )
    elif (
        ("lesion redonda" in respuestas or "lesión redonda" in respuestas)
        and "borde rojo" in respuestas
    ):
        return (
            "Tiña",
            "Antimicótico tópico",
            "Aplica clotrimazol o terbinafina localmente durante 2 semanas."
        )
    elif (
        "ampolla" in respuestas
        and ("labio" in respuestas or "genitales" in respuestas)
    ):
        return (
            "Herpes simple",
            "Antiviral tópico u oral",
            "Inicia aciclovir tópico o valaciclovir oral según prescripción."
        )
    elif (
        "bultos" in respuestas
        and "duros" in respuestas
    ):
        return (
            "Verrugas",
            "Tratamiento tópico o crioterapia",
            "Aplica ácido salicílico o valora crioterapia con dermatólogo."
        )
    else:
        return None, None, None


def diagnostico_otorrinolaringologico(respuestas):
    respuestas = respuestas.lower()
    if (
        "ojos rojos" in respuestas
        and ("picazon" in respuestas or "picazón" in respuestas)
        and "secrecion" in respuestas
    ):
        return (
            "Conjuntivitis",
            "Higiene + evitar contacto",
            "Lava con soluciones salinas y evita frotar. Consulta si hay secreción purulenta."
        )
    elif (
        ("dolor de oido" in respuestas or "dolor de oído" in respuestas)
        and "fiebre" in respuestas
        and "tapado" in respuestas
    ):
        return (
            "Otitis",
            "Evaluación médica (especialmente en niños)",
            "Consulta pronto para antibióticos si está indicado y analgésicos para el dolor."
        )
    elif (
        "presion en cara" in respuestas
        and "secrecion nasal espesa" in respuestas
        and "dolor de cabeza" in respuestas
    ):
        return (
            "Sinusitis",
            "Tratamiento ambulatorio",
            "Descongestionantes y antibiótico si persiste más de 10 días."
        )
    elif (
        ("vision borrosa" in respuestas or "visión borrosa" in respuestas)
        and "halos" in respuestas
        and "dolor ocular" in respuestas
    ):
        return (
            "Glaucoma",
            "Evaluación urgente",
            "Agudeza visual y presión intraocular con oftalmólogo de inmediato."
        )
    elif (
        "dificultad para ver" in respuestas
        and ("vision nublada" in respuestas or "visión nublada" in respuestas)
    ):
        return (
            "Cataratas",
            "Derivación oftalmológica",
            "Consulta oftalmológica para valorar cirugía de cataratas."
        )
    elif (
        "zumbido" in respuestas
        or "disminucion auditiva" in respuestas
        or "disminución auditiva" in respuestas
    ):
        return (
            "Pérdida auditiva",
            "Evaluación ORL o audiometría",
            "Realiza audiometría y consulta con otorrinolaringólogo para rehabilitación auditiva."
        )
    else:
        return None, None, None



def diagnostico_ginecologico(respuestas):
    respuestas = respuestas.lower()
    if (
        "dolor al orinar" in respuestas
        and ("orina turbia" in respuestas or "turbia" in respuestas)
        and "fiebre" in respuestas
    ):
        return (
            "Cistitis",
            "Hidratación + atención médica si persiste",
            "Bebe abundante agua y consulta si hay sangre o dolor severo."
        )
    elif (
        "flujo anormal" in respuestas
        and ("picazon" in respuestas or "picazón" in respuestas or "ardor" in respuestas)
    ):
        return (
            "Vaginitis",
            "Evaluación ginecológica ambulatoria",
            "Toma muestra de flujo y pide tratamiento según cultivo."
        )
    elif (
        ("dolor pelvico" in respuestas or "dolor pélvico" in respuestas)
        and ("menstruacion dolorosa" in respuestas or "menstruación dolorosa" in respuestas)
    ):
        return (
            "Endometriosis",
            "Control ginecológico recomendado",
            "Ultrasonido pélvico y manejo hormonal con tu ginecólogo."
        )
    elif (
        "irritabilidad" in respuestas
        and "dolor mamario" in respuestas
        and "cambios premenstruales" in respuestas
    ):
        return (
            "Síndrome premenstrual (SPM)",
            "Manejo con hábitos y control hormonal",
            "Lleva registro de tu ciclo, dieta equilibrada y valora anticonceptivos hormonales."
        )
    elif (
        "dolor testicular" in respuestas
        or ("dolor" in respuestas and "perineal" in respuestas)
    ):
        return (
            "Prostatitis",
            "Evaluación médica inmediata (urología)",
            "Antibióticos según urocultivo y manejo del dolor con antiinflamatorios."
        )
    else:
        return None, None, None


def diagnostico_digestivo(respuestas):
    respuestas = respuestas.lower()
    if (
        "acidez" in respuestas
        and "ardor" in respuestas
        and ("comer" in respuestas or "aliment" in respuestas)
    ):
        return (
            "Reflujo gastroesofágico (ERGE)",
            "Control dietético + posible medicación",
            "Evita alimentos grasos, eleva la cabecera de la cama y considera IBP según médico."
        )
    elif (
        "diarrea" in respuestas
        and "dolor abdominal" in respuestas
    ):
        return (
            "Colitis",
            "Observación + evitar irritantes",
            "Hidratación con sales y dieta BRAT. Consulta si hay sangre o fiebre alta."
        )
    elif (
        ("evacuaciones dificiles" in respuestas or "evacuaciones difíciles" in respuestas)
        and "dolor abdominal" in respuestas
    ):
        return (
            "Estreñimiento",
            "Hidratación + fibra + hábitos",
            "Aumenta fibra y agua, realiza ejercicio y valora laxantes suaves."
        )
    elif (
        "dolor al evacuar" in respuestas
        and ("sangrado" in respuestas or "sangre" in respuestas)
        and ("picazon" in respuestas or "picazón" in respuestas)
    ):
        return (
            "Hemorroides",
            "Higiene + dieta + evaluación médica si persiste",
            "Baños de asiento, crema de hidrocortisona y dieta rica en fibra."
        )
    elif (
        "gases" in respuestas
        and ("hinchazon" in respuestas or "hinchazón" in respuestas)
        and "diarrea" in respuestas
        and ("lacteos" in respuestas or "lácteos" in respuestas)
    ):
        return (
            "Intolerancia a la lactosa",
            "Evitar lácteos + prueba de tolerancia",
            "Sustituye por leches sin lactosa y realiza test de hidrógeno espirado."
        )
    else:
        return None, None, None

diagnostico_saludmental = diagnostico_salud_mental
