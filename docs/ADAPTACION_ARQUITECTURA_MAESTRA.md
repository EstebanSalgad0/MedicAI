# Adaptación de la «Arquitectura funcional maestra» a MedicAI (APS · Maule)

Documento de trabajo para el equipo. Toma la maqueta de funcionalidades inspirada en referentes
internacionales, latinoamericanos y chilenos (v1.0, 21-10-2026) y propone cómo incorporarla a MedicAI
**sin salir del alcance de la formulación FONDEF** y cumpliendo la normativa chilena.

---

## 1. Conclusiones

1. **La maqueta apunta a un hospital; MedicAI está formulado para APS.** Urgencias, camas, pabellones,
   GRD y costo por episodio pertenecen al nivel secundario y terciario. ANID ya observó
   *inconsistencias entre APS y niveles secundarios* (P1.1, nota 2,5). Incorporar esos paneles ahora
   repetiría la observación. **Propuesta:** adoptar todo lo que sirve al paciente de CESFAM y dejar la
   gestión hospitalaria como **fase de escalamiento**, en un proyecto o convenio aparte con el Hospital
   Regional de Talca.
2. **Cerca de la mitad ya existe.** Agenda con confirmación de asistencia, orientación por nivel de
   atención, guía de ruta GES, recordatorios con adherencia, stock y aviso de reposición, detector de
   emergencias, encuesta y dashboard. Lo que falta son ampliaciones, no reescrituras.
3. **Falta la base legal antes de sumar módulos.** Hoy no hay consentimiento informado en el primer
   contacto ni verificación de identidad (el paciente es su número de teléfono). Cualquier módulo que
   toque datos personales de salud (resultados, FONASA, modo cuidador) depende de esto.
4. **Lo nuevo con más valor para el proyecto** son las funciones que agregan desarrollo propio, que es
   lo que ANID echó de menos en P1.2: *fill-the-gap* con priorización auditable, modo cuidador, bandeja
   de derivación a un funcionario, canal SMS/voz rural y un dashboard que responde preguntas en
   lenguaje natural. Cada una se puede plantear como hipótesis medible.

---

## 2. Qué existe, qué se amplía y qué queda fuera

**Leyenda:** ✅ ya existe · 🔧 ampliar lo existente · 🆕 nuevo · ⏸️ fuera del alcance APS (escalamiento)

### 2.1 Chatbot

| Capacidad de la maqueta | MedicAI hoy | Adaptación para APS en Chile | Estado |
|---|---|---|---|
| Detector de emergencias | Detecta urgencia y riesgo de salud mental antes que cualquier modelo; deriva al 131 | Validar la lista de señales con el equipo clínico. Agregar la línea de prevención del suicidio **\*4141** de MINSAL al mensaje de salud mental | 🔧 |
| Agenda: agendar, reprogramar, cancelar | 13 prestaciones APS, cupos reales, reagendar y cancelar | Conectar con la **agenda real del CESFAM** (hoy MedicAI tiene su propia agenda). Es la integración más importante del piloto | 🔧 |
| Recordatorios 48 h y 24 h con confirmación | Uno, el día anterior, con «Asistiré / Reagendar / No podré ir» | Sumar el de 48 h (configurable). Requiere plantillas aprobadas por WhatsApp | 🔧 |
| Re-agendamiento tras inasistencia | El funcionario marca «No asistió» en el dashboard | Al marcar la inasistencia, el bot ofrece reagendar en 2 toques | 🔧 |
| **Fill-the-gap** (cupo liberado → siguiente en espera) | No existe | Al cancelarse una hora, ofrecerla a pacientes compatibles **según el criterio de priorización del CESFAM** (no al primero que responda), con plazo de respuesta y registro auditable. Indicador: horas recuperadas | 🆕 |
| «¿Qué número voy en la lista?» | No existe | Solo lectura y solo si el CESFAM o el Servicio de Salud entregan los datos de lista de espera. Sin datos oficiales, no se ofrece | 🆕 (depende de datos) |
| Triaje de síntomas | 12 categorías → nivel de atención (urgencia, prioritario, CESFAM, autocuidado), con botón para agendar | Agregar edad, embarazo y enfermedades crónicas como modificadores de riesgo, con revisión clínica. **No** codificar CIE-10 ni sugerir diagnósticos: la maqueta lo propone, pero eso es acto clínico | 🔧 |
| Prechequeo antes de la consulta («gemelo del paciente») | No existe | Motivo de consulta, medicamentos actuales y alergias declarados por el paciente, visibles para el profesional antes de la atención, marcados como «autorreportado» | 🆕 |
| Navegador de la red («¿a dónde voy?») | Guía de ruta GES y no GES, directorio de urgencias por comuna | Agregar horarios y dirección de SAPU/SAR. Tiempos de espera en vivo solo si el Servicio de Salud los publica | 🔧 |
| Trámites FONASA | No existe | **Informativo**, con enlaces oficiales: inscripción en el CESFAM (per cápita), certificado de afiliación, tramos, garantías GES. En APS municipal la atención es gratuita para FONASA, así que la compra de bonos aplica poco | 🆕 |
| Estado de licencia médica | No existe | Solo explicar plazos y dónde consultar. Consultar el estado exige un convenio con la institución responsable y autenticación fuerte | 🆕 (informativo) |
| Notificación de resultados | No existe | Avisar «tu resultado está disponible» y cómo verlo o retirarlo, **sin el contenido**: WhatsApp no es un canal apto para datos clínicos (Ley 20.584 y transferencia internacional a Meta) | 🆕 (requiere integración) |
| Recordatorios de medicación y farmacia | Tomas con confirmación (adherencia), retiros programados, aviso de reposición | Agregar un aviso para renovar la receta crónica antes de que venza | 🔧 |
| Crónicos (presión, glucemia, peso) | No existe | Registro voluntario para llevar al control del programa cardiovascular (PSCV). **Sin alertas clínicas automáticas** hasta acordar un protocolo con el equipo: una alerta crea una obligación de respuesta | 🆕 |
| Salud mental | Detecta riesgo y entrega un mensaje con líneas de ayuda | Chequeo breve de ánimo **solo con protocolo y derivación del equipo de salud mental del CESFAM** (Ley 21.331). Sin terapia conversacional: queda fuera por riesgo | 🔧 |
| Derivación a una persona | Tras 2 mensajes no entendidos, ofrece Salud Responde y el SOME | **Bandeja en el dashboard** para el SOME u OIRS: la conversación llega con su resumen y el funcionario responde por el mismo WhatsApp dentro de la ventana de 24 h | 🆕 |
| Videoconsulta / Hospital Digital | No existe | Derivar con información y enlace a Hospital Digital o Salud Responde; no integrarse | ⏸️ |
| Encuesta de satisfacción | Encuesta 1 a 5 y vista de satisfacción por trámite | Mantenerla. Agregar una pregunta abierta solo cuando la nota sea baja | ✅ |
| Reclamos y sugerencias | No existe | Recibirlos por el chat y **derivarlos a la OIRS**, entregando un número de seguimiento. No reemplaza el reclamo formal de la Ley 20.584 | 🆕 |
| **Modo cuidador** | No existe | Un familiar gestiona horas y recordatorios del paciente con **autorización expresa, registrada y revocable** del propio paciente (o de su representante legal). Sin acceso a resultados | 🆕 |
| Canal SMS / voz rural | Solo WhatsApp y simulador web | La arquitectura ya separa canal y lógica. Agregar un adaptador SMS y luego uno de voz (IVR) reutiliza todos los microservicios | 🆕 |
| Autenticación con ClaveÚnica | Identidad = número de teléfono | ClaveÚnica requiere convenio de una institución pública (Servicio de Salud o municipio), no de la universidad. Mientras tanto: validar el RUT una vez con el SOME o con un código de verificación | 🆕 |
| Consentimiento informado digital | **No existe** | Primer mensaje con aviso de privacidad, finalidad y aceptación explícita; registro con fecha; comando para revocar y pedir la eliminación de datos | 🆕 **obligatorio** |

### 2.2 Dashboard

| Panel de la maqueta | MedicAI hoy | Adaptación para APS | Estado |
|---|---|---|---|
| Paciente / chatbot | Resolución, intenciones, satisfacción, tiempos, uso por servicio | Separar la resolución de **trámites que inicia el paciente** de las respuestas de un toque a avisos (hoy inflan el indicador) | 🔧 |
| Agenda e inasistencia | Horas, estados, tasa de inasistencia | Inasistencia por programa y por prestación; horas recuperadas por fill-the-gap | 🔧 |
| Farmacia | Stock crítico y aviso de reposición | Vencimientos, solo si el sistema de farmacia los entrega | 🔧 |
| Listas de espera | No existe | Solo con datos oficiales del CESFAM o Servicio de Salud | 🆕 (depende de datos) |
| Uso apropiado de niveles de atención | Reparto de orientaciones por nivel | Seguimiento a las 48 h: «¿dónde consultaste finalmente?», para comparar con la recomendación | 🔧 |
| **Analítica conversacional** | No existe | Preguntas en lenguaje natural sobre indicadores **agregados y seudonimizados** («¿cómo va la inasistencia este mes?») → respuesta y gráfico. El LLM nunca ve datos de pacientes | 🆕 |
| Urgencias, camas, quirófano, GRD, financiero | — | Nivel hospitalario | ⏸️ |
| RPA de bonos y reportes DEIS | — | Fuera del alcance APS del chatbot | ⏸️ |

---

## 3. Marco legal que aplica

> Esta tabla orienta el diseño; **no reemplaza la revisión de un abogado** ni la del Comité Ético Científico.

| Norma | Qué exige, en lo que nos toca | Qué implica para MedicAI |
|---|---|---|
| **Ley 21.719** de protección de datos personales (vigencia plena desde el 1 de diciembre de 2026; mientras tanto rige la Ley 19.628) | Los datos de salud son sensibles: base de licitud (consentimiento expreso o mandato legal), deber de informar, derechos de acceso, rectificación, supresión, oposición y portabilidad, medidas de seguridad, evaluación de impacto para tratamientos de alto riesgo, reglas para transferir datos al extranjero | Consentimiento en el primer contacto; derechos ejercibles desde el chat; registro de tratamientos; evaluación de impacto antes del piloto; cláusulas con Meta y con el proveedor del LLM, o un LLM local |
| **Ley 20.584** de derechos y deberes de los pacientes | Confidencialidad de la ficha clínica, información comprensible, representación del paciente, procedimiento de reclamos (OIRS) | No enviar contenido clínico por WhatsApp; reglas del modo cuidador; reclamos derivados a la OIRS |
| **Ley 21.663** Marco de Ciberseguridad | Las instituciones de salud son servicios esenciales: gestión de riesgos, plan de respuesta y notificación de incidentes a la ANCI en plazos breves | Si lo opera el Servicio de Salud: plan de incidentes, respaldos, registros de acceso, TLS y usuarios por servicio (ya en la lista de pendientes) |
| **Ley 21.331** de salud mental | Derechos de las personas con condiciones de salud mental | El módulo de ánimo solo detecta y deriva; sin intervenciones terapéuticas |
| **Ley 19.966** (GES) | Garantías explícitas de acceso, oportunidad y protección financiera | El bot informa y orienta; no certifica garantías |
| **Ley 21.541** de telemedicina | Regula las prestaciones de salud a distancia | MedicAI no es teleconsulta; si algún día se agrega, debe cumplirla |
| **Ley 21.180** de transformación digital del Estado | Trámites digitales y ClaveÚnica en organismos públicos | ClaveÚnica entra por la institución pública asociada |
| **Ley 20.120** (investigación en seres humanos) | Aprobación de un Comité Ético Científico | Necesaria para el piloto con pacientes; ya figura como pendiente |
| Regulación de dispositivos médicos (ISP) | Un software que orienta decisiones clínicas puede considerarse dispositivo médico | Mantener la orientación como **informativa**, con reglas revisadas clínicamente, y consultar al ISP antes de escalar el triaje |

---

## 4. Hoja de ruta adaptada

| Fase | Chatbot | Dashboard | Requisito legal o técnico | Cómo sabremos que funcionó |
|---|---|---|---|---|
| **0 · Antes del piloto** (4–6 semanas) | Consentimiento y aviso de privacidad; revocación y eliminación por chat; validación de RUT; \*4141 en salud mental | Separar la resolución de trámites iniciados por el paciente | Evaluación de impacto, Comité Ético, plantillas de WhatsApp, revisión clínica de las reglas | 100 % de los usuarios con consentimiento registrado |
| **1 · Piloto APS** (2–3 meses) | Recordatorio de 48 h, re-agendamiento tras inasistencia, **fill-the-gap v1**, bandeja de derivación a funcionario, FONASA e inscripción (informativo), reclamos a la OIRS | Horas recuperadas, inasistencia por programa, bandeja de derivaciones | Integración con la agenda del CESFAM | Inasistencia ≤ 10 % en el CESFAM piloto frente a su línea base; ≥ 80 % de resolución en trámites iniciados por el paciente |
| **2 · Ampliación** (3–6 meses) | Modo cuidador, prechequeo, chequeo de ánimo con protocolo, registro PSCV, aviso de resultados (sin contenido), renovación de receta | **Analítica conversacional**, seguimiento de uso apropiado de niveles | Convenio para resultados; protocolo de salud mental | Precisión del NLU y del aviso de resultados medidos con protocolo |
| **3 · Escalamiento** (fuera del FONDEF actual) | Canal SMS y voz rural; réplica en otros CESFAM del Maule | Paneles hospitalarios (urgencias, camas, pabellón) junto al Hospital Regional | Convenio con el Servicio de Salud del Maule; ClaveÚnica institucional | Modelo replicable en otros Servicios de Salud |

---

## 5. Cómo responde esto a las observaciones de ANID

| Observación | Lo que aporta la adaptación |
|---|---|
| **P1.1** APS vs. niveles secundarios | El alcance se mantiene en APS; lo hospitalario queda explícitamente como escalamiento |
| **P1.2** Tecnologías maduras, sin desarrollo propio | Hipótesis nuevas: ¿el fill-the-gap con priorización recupera horas sin afectar la equidad?, ¿el canal SMS o voz aumenta el uso en zonas rurales?, ¿la analítica conversacional responde correctamente preguntas de gestión? |
| **P2.1** Atributos solo operativos | Atributos medibles: horas recuperadas, inasistencia con y sin recordatorio de 48 h, uso apropiado a las 48 h, precisión de la analítica conversacional |
| **P2.4** Competencias en interoperabilidad y ciberseguridad | Plan explícito de integración (agenda del CESFAM, farmacia, resultados) con estándares HL7 FHIR y medidas de la Ley 21.663 |

---

## 6. Cuidados antes de usar la maqueta en una postulación

- **Cifras de los referentes.** Datos como «13 M usuarios», «−50 % de visitas a urgencia», «50 % de
  auto-resolución» o «95 % por bot» deben citarse con su fuente primaria y año, o eliminarse.
- **Afirmaciones absolutas.** «Ningún referente combina…» es difícil de sostener ante un panel; conviene
  decir «no identificamos en la revisión un referente que combine…».
- **Funciones clínicas.** La codificación CIE-10 automática, la TCC conversacional y las alertas
  clínicas automáticas cambian el carácter del sistema: de herramienta informativa a una con
  responsabilidad clínica. Dejarlas fuera, o condicionarlas a un protocolo validado, protege al proyecto.
