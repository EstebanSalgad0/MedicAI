# MedicAI — Agente IA para la gestión del acceso en Atención Primaria de Salud

Asistente conversacional por WhatsApp para pacientes de CESFAM de la Región del Maule, con un
panel de indicadores para los equipos de salud. Construido como **microservicios en contenedores
Docker**, con un **NLU híbrido (Rasa NLU + LLM de respaldo)** y telemetría que mide en vivo los
atributos comprometidos en la formulación FONDEF IDeA I+D.

| Microservicio | Qué resuelve para el paciente |
|---|---|
| `ms-agendamiento` | Reservar, reagendar y cancelar horas de APS; recordatorio con confirmación de asistencia el día anterior |
| `ms-recordatorios` | Recordatorios de toma de medicamentos; cada dosis se confirma (tomada / omitida / pospuesta) → indicador de adherencia |
| `ms-orientacion` | Orientación inicial de síntomas en 12 categorías: sugiere **nivel de atención** (urgencia, prioritario, CESFAM, autocuidado). No diagnostica |
| `ms-derivacion` | Guía de ruta para interconsultas (GES / no GES), exámenes, recetas y derivaciones urgentes, con seguimiento a 7 días |
| `ms-medicamentos` | Disponibilidad de fármacos por CESFAM, retiros programados (únicos o cíclicos) y aviso de reposición de stock |

Más el núcleo: `whatsapp-gateway`, `orchestrator`, `nlu` + `nlu-rasa`, `analytics`, `scheduler`,
`dashboard` y un `gateway` nginx, sobre PostgreSQL (una base por servicio) y Redis.
Detalle en [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) y relación con la postulación en
[docs/ALINEACION_FORMULACION.md](docs/ALINEACION_FORMULACION.md).

## Puesta en marcha

Requisitos: Docker 24+ con Docker Compose v2.

```bash
cp .env.example .env          # completa al menos POSTGRES_PASSWORD, DASHBOARD_PASSWORD, JWT_SECRET, ANALYTICS_SALT, INTERNAL_TOKEN
docker compose up -d --build  # la primera vez entrena el modelo Rasa dentro de la imagen (unos minutos)
docker compose ps             # todos los servicios deben quedar "healthy" / "running"
```

- **Dashboard:** http://localhost:8080 (usuario y clave de `DASHBOARD_USER` / `DASHBOARD_PASSWORD`).
- **Simulador:** pestaña *Simulador* del dashboard. Permite probar todos los flujos sin WhatsApp; esas
  conversaciones quedan con canal «Simulador» y se pueden excluir de los indicadores.
- **Sin credenciales de WhatsApp** el gateway arranca en modo `DRY_RUN`: procesa todo y registra los
  mensajes en el log en vez de enviarlos.

### Conectar WhatsApp Business (Cloud API)

1. En Meta for Developers, copia el *token de acceso*, el *Phone number ID* y el *App Secret* al `.env`
   (`WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_APP_SECRET`) y define un `WHATSAPP_VERIFY_TOKEN`.
2. Expón el puerto 8080 con HTTPS (proxy del servidor institucional o un túnel) y registra el webhook
   `https://<dominio>/webhook` con el mismo verify token. Suscribe el campo `messages`.
3. `docker compose up -d whatsapp-gateway` y escribe «hola» al número.

> Los recordatorios proactivos (tomas, horas, retiros) fuera de la ventana de 24 h de WhatsApp requieren
> **plantillas aprobadas por Meta**. Es un trámite a gestionar antes del piloto con pacientes.

### Activar el LLM de respaldo (opcional)

Por defecto el NLU usa Rasa y, si Rasa duda, un clasificador de reglas. Para sumar un LLM:

```env
LLM_PROVIDER=anthropic      # o "openai" para cualquier API compatible (p. ej. Ollama en el servidor del Servicio de Salud)
LLM_API_KEY=...
LLM_MODEL=claude-haiku-5-5
```

El LLM solo elige una intención de una lista cerrada; nunca redacta respuestas al paciente ni decide
orientación clínica. Antes de enviar texto se enmascaran RUT, teléfonos y correos. Con `openai` +
Ollama local los datos no salen de la infraestructura.

## Validación y evidencia

```bash
# Pruebas unitarias de cada servicio
for s in services/*/; do [ -d "$s/tests" ] && (cd "$s" && python -m pytest -q tests); done

# Pruebas funcionales del sistema completo (guiones de conversación por el gateway)
python scripts/simular_conversaciones.py --url http://localhost:8080 --password <clave> --repeticiones 3

# Precisión del NLU sobre el conjunto reservado (exactitud, F1 macro, fallback, latencia por capa)
docker compose exec nlu-rasa rasa test nlu --nlu tests/test_nlu.yml      # solo Rasa
python scripts/evaluar_nlu.py --nlu http://<host-nlu>:8000 --salida reporte_nlu.json   # pipeline híbrido
```

El dashboard (pestaña *Indicadores*) muestra cada meta con su numerador y denominador y permite
**exportar a CSV** los eventos seudonimizados para el análisis estadístico.

## Desarrollo local sin Docker

Cada servicio es una app FastAPI independiente que, sin `DATABASE_URL`, usa SQLite y, sin `REDIS_URL`,
guarda sesiones en memoria:

```bash
pip install -e libs/medicai_common fastapi "uvicorn[standard]" sqlalchemy httpx redis PyJWT pyyaml pytest
cd services/ms-agendamiento && uvicorn app.main:app --port 8101 --reload   # docs en /docs
cd dashboard && npm install && npm run dev                                  # proxy /api -> localhost:8080
```

## Estructura

```
libs/medicai_common/     contrato de diálogo, mensajes, eventos, utilidades compartidas
services/<servicio>/     app/ (código), tests/, Dockerfile, requirements.txt
services/nlu-rasa/       datos de entrenamiento, configuración y conjunto de prueba de Rasa
dashboard/               React + Vite
infra/                   nginx (API gateway) y bootstrap de PostgreSQL
scripts/                 simulación de conversaciones y evaluación del NLU
legacy/                  prototipo monolítico original (Flask), conservado como referencia
```
