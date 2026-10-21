# Arquitectura de MedicAI

## Vista general

```mermaid
flowchart LR
    P([Paciente<br/>WhatsApp]) -->|webhook| GW
    F([Funcionario APS<br/>navegador]) --> GW

    subgraph borde[Borde]
        GW[gateway<br/>nginx · JWT · rate limit]
    end

    GW -->|/webhook| WA[whatsapp-gateway<br/>firma Meta · deduplicación · reintentos]
    GW -->|/| DASH[dashboard<br/>React]
    GW -->|/api/*| AN

    WA --> ORQ[orchestrator<br/>sesiones · enrutamiento · métricas]
    ORQ --> NLU[nlu<br/>híbrido]
    NLU --> RASA[nlu-rasa<br/>Rasa NLU · DIET]
    NLU -.->|si Rasa duda| LLM[(LLM<br/>opcional)]

    ORQ --> AGD[ms-agendamiento]
    ORQ --> REC[ms-recordatorios]
    ORQ --> ORI[ms-orientacion]
    ORQ --> DER[ms-derivacion]
    ORQ --> MED[ms-medicamentos]

    SCH[scheduler] -->|tick cada 60 s| AGD & REC & DER & MED
    AGD & REC & DER & MED -->|mensajes proactivos| WA

    ORQ & AGD & REC & ORI & DER & MED & WA -->|eventos| AN[analytics<br/>KPIs · auth]

    ORQ --- REDIS[(Redis<br/>sesiones)]
    WA --- REDIS
    AGD --- PG[(PostgreSQL<br/>1 base por servicio)]
    REC --- PG
    DER --- PG
    MED --- PG
    AN --- PG
```

Solo el contenedor `gateway` publica un puerto. Todo lo demás vive en la red interna `backend`.

## Recorrido de un mensaje

1. Meta envía el webhook → nginx → `whatsapp-gateway`. Se verifica la firma `X-Hub-Signature-256`,
   se descarta si el `message_id` ya se procesó (Meta reintenta) y se responde 200 de inmediato.
2. En segundo plano el gateway llama a `orchestrator /message`.
3. El orquestador evalúa **señales de alarma** primero (palabras clave deterministas: dolor torácico,
   dificultad respiratoria, ideación suicida…). Si hay una, responde con 131 / \*4141 sin pasar por modelos.
4. Si el paciente tocó un botón, el prefijo del id (`agd:`, `rec:`, `ori:`, `der:`, `med:`) decide el
   servicio. Si escribió texto dentro de un trámite, el texto va a ese servicio. Si no, se consulta el NLU.
5. El microservicio responde con mensajes **independientes del canal**, su nuevo estado y eventos de
   dominio. El orquestador guarda el estado en Redis (TTL 30 min) y emite la telemetría.
6. El gateway traduce los mensajes al formato de WhatsApp (respetando límites de 3 botones, 10 filas,
   1.024 caracteres) y los envía con reintentos ante 429/5xx.

## Contrato entre orquestador y microservicios

`POST /dialog` en cada microservicio (definido en `libs/medicai_common/contracts.py`):

```jsonc
// DialogRequest
{ "user_id": "569…", "channel": "whatsapp", "text": "…", "option_id": "agd:center:las_americas",
  "intent": "agendar_cita", "entities": {"prestacion": "matrona"}, "state": {…}, "start": false }
// DialogResponse
{ "messages": [{"type": "list", "text": "…", "options": [{"id": "agd:slot:…", "title": "…"}]}],
  "state": {…} | null,            // null = trámite terminado
  "resolved": true,               // terminó sin intervención humana
  "events": [{"type": "appointment_booked", "center": "las_americas", "props": {…}}],
  "handoff": {"service": "recordatorios", "entities": {"medicamento": "Losartán"}} | null }
```

Los servicios no guardan sesiones (el estado viaja en el contrato), por lo que escalan
horizontalmente. Un servicio puede derivar al paciente a otro con `handoff` (p. ej. tras programar un
retiro en farmacia, ofrecer recordatorios de toma).

## NLU híbrido

| Capa | Cuándo actúa | Por qué |
|---|---|---|
| Detector de alarmas | Siempre, primero | Seguridad: no puede depender de la confianza de un modelo |
| Rasa NLU (DIET + n-gramas de caracteres) | Confianza ≥ `RASA_CONFIDENCE_THRESHOLD` (0,70) | Modelo propio, entrenado con español de Chile, sin costo por consulta, auditable |
| LLM (opcional) | Rasa duda | Cubre redacciones no vistas; elige de una lista cerrada de intenciones |
| Reglas por palabras clave | Rasa y LLM no disponibles | El sistema sigue operando en modo degradado |

Cada interacción registra qué capa resolvió, su confianza y su latencia: con eso se mide el aporte de
cada componente de IA (`scripts/evaluar_nlu.py` y gráfico «¿Quién interpretó los mensajes?»).

## Datos y privacidad (Ley 21.719)

- **Base por servicio.** Ningún servicio lee la base de otro.
- **Analítica seudonimizada.** `analytics` guarda un hash salado del teléfono, nunca el número ni el
  texto de los mensajes. Los eventos no incluyen nombres de medicamentos ni síntomas.
- **LLM con minimización.** Se enmascaran RUT, teléfonos y correos; se puede usar un LLM local.
- **Endpoints internos** (`/dialog`, `/internal/*`) bloqueados en el gateway y protegidos con
  `INTERNAL_TOKEN`; el dashboard exige JWT; el login tiene límite de intentos.

## Indicadores que se calculan

| Indicador | Definición | Meta |
|---|---|---|
| Tiempo de respuesta p95 | Percentil 95 del procesamiento por mensaje (más p95 extremo a extremo del webhook) | ≤ 5 s |
| Resolución autónoma | Trámites completados con `resolved=true` / trámites iniciados | ≥ 85 % |
| Satisfacción | Promedio de la encuesta 1-5 enviada al completar un trámite (máx. 1 cada 24 h) | ≥ 4,5 |
| Mensajes no entendidos | Mensajes de texto interpretados por el NLU que terminan en fallback / total | < 8 % |
| Adherencia | Dosis confirmadas como tomadas / (tomadas + omitidas + sin respuesta en 6 h) | ≥ 70 % |
| Inasistencia | No asistió / (asistió + no asistió), registrado por funcionarios en *Agenda* | línea base |

## Escalabilidad y operación

- Servicios stateless detrás del orquestador → se replican con `docker compose up --scale ms-orientacion=3`
  (o migrando a Kubernetes sin cambiar código).
- El `scheduler` reemplaza el hilo en memoria del prototipo: las tareas son idempotentes
  (`dose_logs` con restricción única) y sobreviven a reinicios.
- Cada imagen tiene `HEALTHCHECK`; Compose reinicia contenedores caídos.
- Pendiente para producción: migraciones con Alembic, usuarios de base de datos por servicio,
  backups programados de PostgreSQL, TLS en el gateway y plantillas de WhatsApp aprobadas.
