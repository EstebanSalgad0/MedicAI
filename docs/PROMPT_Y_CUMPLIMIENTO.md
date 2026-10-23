# System prompt de MedicAI y dónde se cumple cada regla

El system prompt de Marcos Cereceda Otarola y Esteban Salgado (Parte B, versión corregida) es la especificación
de comportamiento de MedicAI. Su texto está en
[`libs/medicai_common/medicai_common/prompts.py`](../libs/medicai_common/medicai_common/prompts.py) y es la
única copia que usa el código.

**Criterio de diseño:** una regla del prompt que protege al paciente no puede depender solo de que el modelo
la obedezca. Por eso cada regla se cumple **en el código** (permisos, alarmas, citas, validaciones), y el
prompt se entrega además al modelo local cuando se usa. Si el modelo se equivoca, el código descarta su
salida.

`para_modulo(n)` arma el prompt de cada módulo con el núcleo común (rol, principios, acceso, formato y límites)
más el módulo correspondiente. Un médico y un paciente no reciben las mismas instrucciones.

## Principios fundamentales

| Regla del prompt | Cómo se cumple | Dónde |
|---|---|---|
| Seguridad primero; ante alarma, derivar de inmediato | Detector de alarmas por reglas, antes del NLU y de cualquier modelo. Tarjeta con SAMU 131 / \*4141 | `medicai_common/safety.py`, `orchestrator/app/main.py` |
| Trazabilidad total: establecimiento, expediente, fecha y sección | Cada `Registro` lleva una `Cita` desde la fuente y la respuesta la muestra con el formato `[Establecimiento · Exp. N° · dd-mm-aaaa · sección, p. N]` | `ms-historial/app/fuentes.py` |
| Cero alucinaciones: decir «no se encontró» | Las secciones vacías se informan con «No se encontró … en las fuentes disponibles (…)». Las bases que no responden se informan aparte | `ms-historial/app/perfil.py` |
| Nunca inventar valores | Los valores salen tal cual de la fuente. Una hipótesis del modelo que no cita un registro existente se descarta. Un dictado reordenado por el modelo con texto que no estaba en la transcripción se descarta | `ms-historial/app/ia.py`, `ms-historial/app/dictado.py` |
| El médico decide | Las hipótesis empiezan con «Hipótesis a considerar» y llevan «Requiere confirmación del médico tratante». Las alertas usan «Sugerido evaluar». La ficha queda en borrador hasta que el profesional la firma | `ms-historial/app/clinica.py`, `main.py` |
| Privacidad (Ley 19.628 y Ley 20.584) | Permisos por rol y relación asistencial, auditoría de cada acceso, analítica seudonimizada, datos clínicos solo con modelo local | ver abajo |

## Acceso y autenticación

| Regla | Implementación |
|---|---|
| Profesionales y pacientes ingresan con ClaveÚnica | `ms-identidad`: cliente OpenID Connect de ClaveÚnica (`CLAVEUNICA_MODE=produccion`) con un simulador para pruebas (`demo`). Los profesionales reciben un token con rol y establecimientos. Las cuentas locales son solo de administración o gestión y no abren fichas |
| Nunca pedir contraseñas, documentos de identidad ni datos de pago por el chat | El chat ya no pide RUN ni fecha de nacimiento. Resultados, derivaciones y modo cuidador envían un **enlace de un solo uso** (vence en 10 min). El paciente ingresa con ClaveÚnica y su WhatsApp queda vinculado a su RUN. Los datos de la persona a cargo se completan en una página web segura, fuera del chat |
| Verificar rol y permisos sobre el paciente; si no los tiene, indicarlo y detenerse | `ms-historial` exige rol clínico e ingreso con ClaveÚnica. Además exige **relación asistencial**: registros del paciente en un establecimiento del profesional, o una derivación activa hacia él. Sin relación responde 403 con el motivo. El acceso por urgencia se permite y queda marcado como excepcional en la auditoría |

## Módulo 1: Dashboard clínico (`ms-historial` + página *Ficha clínica*)

| Punto del prompt | Implementación |
|---|---|
| 1. Resumen instantáneo | Condiciones activas, medicamentos vigentes, alergias y número de alertas altas, cada uno con su cita. Si un mismo dato aparece en varios establecimientos, se agrupa sin perder las citas |
| 2. Línea de tiempo de exámenes | Orden cronológico, más reciente primero. Lo fuera de rango (según el rango de referencia de la fuente) se marca con ▲/▼, texto y color |
| 3. Alertas clínicas | Controles vencidos, interacciones entre fármacos vigentes (incluso recetados en establecimientos distintos), alergia con fármaco relacionado, dosis distintas entre establecimientos y signos de riesgo en crónicos (HbA1c, VFG con metformina, potasio, control PSCV atrasado). Cada regla tiene un código (INT-, ALG-, CON-, CTL-, RSG-) para trazarla |
| 4. Apoyo diagnóstico | Reglas clínicas configuradas (DX-01…) según el cuadro que escribe el profesional y los registros del paciente. Con modelo local, se suman hipótesis cuyas citas se verifican. Si nada respalda una hipótesis, lo dice |
| 5. Ficha por dictado | Transcripción con un servicio de voz **local** (`ASR_URL`), ordenada en anamnesis, examen físico, diagnóstico (según lo dictado) e indicaciones. No agrega texto; las secciones no dictadas se informan. El profesional edita, guarda el borrador y firma; una vez firmada, la ficha no cambia |
| Consulta multi-establecimiento según la selección | El profesional marca las bases. Se consultan **en paralelo** y cada dato indica su establecimiento |
| Prioridad (a)–(e) en historiales extensos | El perfil se entrega y se muestra en ese orden. El detalle (antecedentes, controles, atenciones) queda plegado y se abre a solicitud |
| Baja latencia e informar el progreso | `/perfil/stream` envía una línea por cada base apenas responde. Las bases lentas se informan como «sin respuesta» al vencer `FUENTE_TIMEOUT_SECONDS`, sin bloquear al resto |

## Módulo 2: Chatbot de pacientes

| Punto del prompt | Implementación |
|---|---|
| Pedir, confirmar y anular horas | `ms-agendamiento` (ya existía) |
| Controles según el perfil (crónicos, niño sano, embarazo, vacunas) | Si el paciente vinculó su identidad, al agendar en su CESFAM se le muestran primero los controles pendientes de su ficha. Solo llega la prestación («tienes un control crónico pendiente»), nunca el diagnóstico |
| Orientación de síntomas y nivel de atención | `ms-orientacion` (ya existía; no diagnostica) |
| Recordatorios con confirmación en un toque | `ms-recordatorios`, `ms-agendamiento` (ya existían) |
| Lenguaje simple y sin diagnósticos | Textos fijos revisables. El modelo nunca redacta respuestas al paciente: solo clasifica la intención |
| Triaje de urgencia: 131 y **ofrecer equipo humano** | Tras la tarjeta de emergencia, botón «🚨 Avisar al equipo». Crea de inmediato una solicitud con tema *urgencia* y la conversación, sin hacer preguntas |
| Traspaso humano obligatorio (lo pide, excede el alcance o emergencia) | «Hablar con persona» en el menú, ofrecimiento automático tras 3 mensajes no entendidos, y emergencia |

## Módulo 3: Agendas y derivaciones

| Punto del prompt | Implementación |
|---|---|
| Todos los box y profesionales en una vista, en tiempo real | `GET /agendamiento/ocupacion`: grilla del día por profesional y box (ocupada, ofrecida, libre, atendida, inasistencia). La página *Agenda* la refresca cada 30 s. La dotación de prueba está en `catalog.dotacion()` |
| Horas anuladas a la lista de espera, por prioridad clínica y orden de llegada | Fill-the-gap con tres niveles: **prioridad clínica** (asignada por el equipo, con motivo y responsable) > GES > antigüedad |
| Explicar el criterio aplicado | Cada oferta guarda su `criterio` (p. ej. «Prioridad clínica asignada por … ; prevalece sobre el orden de llegada (se antepuso a 2 pacientes con más antigüedad)»), visible en *Reasignaciones recientes* |
| Derivaciones intra y extra red con estados enviada / agendada / atendida / caducada | `ms-derivacion`: modelo `Derivacion` con transiciones válidas, historial de eventos y caducidad automática por plazo. El paciente puede consultar el estado con ClaveÚnica y recibe un aviso al agendarse |
| Registrar fecha, origen, destino y responsable | Campos obligatorios. El responsable sale del token del funcionario, nunca de un campo editable |

## Arquitectura técnica

| Punto del prompt | Implementación |
|---|---|
| Modelo 100 % local | `medicai_common/llm.py`: el proveedor por defecto es `ollama` (contenedor del perfil `llm` con GPU). Un proveedor externo queda bloqueado salvo `LLM_ALLOW_EXTERNAL=true`, y **nunca** se usa con datos clínicos |
| Servidores GPU | Servicio `ollama` con reserva de GPU NVIDIA en `docker-compose.yml`. El dimensionamiento lo define ingeniería |
| Consultas multi-base en paralelo | `fuentes.consultar()` con un hilo por establecimiento y tiempo máximo por base |

## Qué no resuelve el software

- **Las reglas clínicas** (interacciones, umbrales, hipótesis) son un punto de partida y deben revisarlas y
  aprobarlas el equipo clínico. Cada una tiene código para su trazabilidad.
- **Las fuentes reales.** El modo `demo` simula los registros. El adaptador FHIR R4 es de referencia: hay que
  validar el mapeo con el sistema de cada establecimiento.
- **ClaveÚnica en producción** requiere las credenciales que entrega la División de Gobierno Digital y una
  URL pública con HTTPS registrada como `redirect_uri`.
- **Marco legal.** El prompt cita las leyes 19.628 y 20.584. Para la operación conviene revisar con
  asesoría legal la Ley 21.719, que reforma la 19.628, y la normativa de interoperabilidad de fichas
  clínicas.
