# Alineación del software con la formulación y la retroalimentación de ANID

Documento de trabajo para el equipo. Contrasta lo que declaran la formulación FONDEF IDeA I+D 2026
(folio ID26I10283) y el Anexo 1 del concurso *Valida tu Invención +UAutónoma* con lo que hacía el
prototipo y con lo que hace esta versión.

## 1. Lo declarado en la postulación vs. el código

| Declaración (formulación §1.5 y Anexo 1 §2.3) | Prototipo original (`legacy/`) | Esta versión |
|---|---|---|
| Docker Compose con contenedores independientes para chatbot, microservicios y BD | Una sola app Flask (`services.py`, 3.030 líneas) desplegada en Heroku; sin Docker | 15 contenedores orquestados con `docker-compose.yml`; un Dockerfile por servicio |
| Microservicios especializados | Funciones dentro de un `if/elif` de ~1.300 líneas | 5 microservicios FastAPI con base de datos propia y contrato `/dialog` común |
| Motor Rasa NLU entrenado en intenciones críticas | Búsqueda de palabras clave | Rasa NLU (DIET) con 18 intenciones y entidades (medicamento, prestación); LLM de respaldo opcional |
| Webhook con manejo de reintentos y errores | Sin deduplicación ni reintentos | Deduplicación por `message_id`, reintentos con backoff, firma de Meta, respuesta 200 inmediata |
| Panel de monitoreo / dashboard web | No existía | Dashboard React: indicadores vs. metas, agenda, farmacia, simulador, exportación CSV |
| Métricas: < 3 s, > 99 % disponibilidad, fallbacks < 8 % | No se registraban: no había forma de respaldarlas | Se miden en cada interacción y se muestran con numerador/denominador; disponibilidad vía healthchecks |
| Integración con sistemas de salud (stock, citas) | Stock simulado con 4 nombres fijos; fechas de cita fijas de 2025 | Adaptador de stock `local`/`http` para el sistema de farmacia; agenda real con cupos y estados |
| Persistencia de recordatorios | Diccionarios en memoria: se perdían al reiniciar | PostgreSQL + scheduler idempotente |

> **Acción para la próxima postulación:** la formulación cita el repositorio
> `UNI2-TrabajoSocial/Chatbot_MedicAI`. Conviene apuntar a este repositorio (o sincronizarlos) para
> que la evidencia que revise el panel corresponda a esta arquitectura.

## 2. Observaciones de ANID y cómo responde el software

| Observación del panel (nota) | Respuesta en el software | Lo que el software NO resuelve solo |
|---|---|---|
| **P1.1 (2,5)** Inconsistencias entre APS y niveles secundarios | Agendamiento ofrece solo prestaciones de APS; especialidades se canalizan como interconsulta en derivación | Ajustar el texto de la formulación con la misma delimitación |
| **P1.2 (2,0)** Tecnologías maduras, sin desarrollo propio ni desafío técnico | NLU híbrido con medición por capa; orquestación de microservicios con traspaso entre servicios; triage clínico explicable. Preguntas de investigación posibles: ¿cuánto aporta el LLM sobre Rasa en español de Chile?, ¿qué umbral de confianza optimiza precisión vs. fallback?, ¿los recordatorios con confirmación mejoran adherencia e inasistencia? | Formular explícitamente esas preguntas como incertidumbres tecnológicas e hipótesis |
| **P1.4 (2,5)** Evidencia TRL insuficiente, sin métricas independientes ni pruebas controladas | `scripts/evaluar_nlu.py` (exactitud, F1, fallback sobre conjunto reservado), `scripts/simular_conversaciones.py` (pruebas funcionales repetibles), telemetría exportable | Ejecutar las pruebas con usuarios reales y reportar resultados con protocolo |
| **P2.1 (2,5)** Atributos solo operativos, sin ventaja tecnológica | Nuevos atributos medibles: precisión de intención, aporte del LLM, adherencia confirmada por dosis, inasistencia con/sin recordatorio, tiempo a contacto de interconsulta | Fijar metas para esos atributos en la formulación |
| **P2.2 (2,5)** Sin protocolo experimental ni control de variables | Canal y CESFAM como dimensiones; eventos con marca de tiempo exportables para comparar grupos (p. ej. CESFAM con y sin recordatorio de asistencia) | Diseñar el protocolo (grupos, tamaño muestral, periodo) |
| **P2.3 (2,0)** Sin recursos para IA, inferencia LLM, cloud o cómputo | Costos ahora identificables: servidor para 15 contenedores, API de LLM (o GPU para LLM local), WhatsApp Business por conversación | Presupuestarlos en la planilla |
| **P2.4 (3,0)** Dudas sobre competencias en LLM, interoperabilidad y ciberseguridad | Arquitectura documentada con controles de seguridad (firma, JWT, aislamiento de red, seudonimización) | Explicitar roles técnicos del equipo |
| **Certificado de ética** requerido | Seudonimización y minimización de datos facilitan el trámite | Gestionar el certificado |

## 3. Correspondencia con los objetivos del Anexo 1

| Objetivo | Cómo apoya esta versión |
|---|---|
| OE1 Encuesta nacional CATI/CAWI | Los resultados pueden priorizar qué microservicio ampliar; la arquitectura permite agregar uno nuevo sin tocar los demás |
| OE2 Entrevistas a actores clave | El simulador sirve para mostrar los flujos durante la entrevista |
| OE3 Validación funcional, interoperabilidad y usabilidad | Simulador con traza técnica, guiones repetibles, adaptador de stock para probar interoperabilidad, encuesta de satisfacción integrada |
| OE4 Parametrización y optimización | Umbral de Rasa, uso de LLM, ventana de recordatorios y encuesta configurables por `.env`; datos de entrenamiento versionados |

## 4. Pendientes antes de un piloto con pacientes

- Plantillas de WhatsApp aprobadas para mensajes proactivos.
- Directorio real de SAPU/SAR (`services/ms-derivacion/app/data/establecimientos_urgencia.json`) validado con las entidades asociadas.
- Revisión clínica de las reglas de orientación (`services/ms-orientacion/app/reglas.py`, endpoint `/rules`).
- Contrato de la API de stock con el sistema de farmacia del CESFAM.
- TLS, backups, usuarios de BD por servicio y migraciones (Alembic).
- Ampliar `services/nlu-rasa/tests/test_nlu.yml` con mensajes reales anonimizados del piloto.
