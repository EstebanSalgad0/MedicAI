# MedicAI: asistente clínico y administrativo para la red asistencial

MedicAI apoya a la red asistencial chilena (APS, atención secundaria y terciaria) del Maule en tres módulos,
según el system prompt de Marcos Cereceda Otarola y Esteban Salgado
([`prompts.py`](libs/medicai_common/medicai_common/prompts.py)). Su principio rector es **apoyar sin decidir**:
toda salida clínica es una sugerencia que valida un profesional.

| Módulo | Para quién | Qué hace |
|---|---|---|
| **1. Dashboard clínico** | Profesionales de salud (ClaveÚnica) | Perfil sintético del paciente desde una o varias bases de la red, consultadas en paralelo y con progreso visible. Incluye resumen, línea de tiempo de exámenes con valores fuera de rango, alertas (interacciones, controles pendientes, riesgo en crónicos), apoyo diagnóstico para validación y ficha por dictado para revisar y firmar. **Cada dato cita su fuente** `[Establecimiento · Exp. · fecha · sección]` y lo que falta se informa como «no se encontró» |
| **2. Chatbot de pacientes** | Pacientes por WhatsApp | Horas, controles según el perfil, orientación de síntomas sin diagnóstico, recordatorios y traspaso humano. Ante una alarma indica 131 y ofrece avisar al equipo. **Nunca pide RUN, claves ni datos de pago por el chat**: la identidad se verifica con ClaveÚnica mediante un enlace seguro |
| **3. Agendas y derivaciones** | Equipos del establecimiento | Ocupación por box y profesional en tiempo real. Reasignación de horas anuladas con prioridad clínica sobre el orden de llegada y el criterio explicado. Derivaciones intra y extra red con estados enviada / agendada / atendida / caducada, y registro de fecha, origen, destino y responsable |

La correspondencia regla por regla entre el prompt y el código está en
[docs/PROMPT_Y_CUMPLIMIENTO.md](docs/PROMPT_Y_CUMPLIMIENTO.md).

| Microservicio | Qué resuelve |
|---|---|
| `ms-historial` | **Módulo 1.** Ficha clínica multi-establecimiento con citas, alertas, apoyo diagnóstico y ficha por dictado. Permisos por rol y relación asistencial, con auditoría de cada acceso |
| `ms-identidad` | **ClaveÚnica** (OpenID Connect) para profesionales y pacientes. Vincula el WhatsApp del paciente con su RUN sin pedirlo por el chat. Incluye el registro web del modo cuidador y el alta de profesionales |
| `ms-agendamiento` | Horas en el **Hospital Regional de Talca** y en **CESFAM**, recordatorios a 48 y 24 h, lista de espera con **prioridad clínica** y fill-the-gap con el criterio registrado, **ocupación por box y profesional** y controles sugeridos según la ficha |
| `ms-derivacion` | Guía de ruta para el paciente y **derivaciones clínicas con seguimiento** (estados, historial, caducidad por plazo, aviso al paciente) |
| `ms-recordatorios` | Recordatorios de toma con dosis y confirmación por dosis, y aviso de renovación de receta |
| `ms-orientacion` | Triaje informativo, orientación por categoría y chequeo de ánimo. No diagnostica |
| `ms-medicamentos` | Disponibilidad de fármacos en CESFAM y Farmacia Hospitalaria, y retiros programados |
| `ms-resultados` | Estado de exámenes (disponible / en proceso) con identidad verificada por ClaveÚnica. Nunca muestra valores |
| `ms-atencion` | Trámites FONASA, información del hospital, **hablar con una persona** (también ante emergencias) y modo cuidador |

Más el núcleo: `whatsapp-gateway`, `orchestrator` (menú, detector de emergencias, modo cuidador y modo gestión),
`nlu` + `nlu-rasa`, `analytics`, `scheduler`, `dashboard`, un `gateway` nginx y, opcionalmente, `ollama`
(modelo de lenguaje **100 % local** con GPU), sobre PostgreSQL (una base por servicio) y Redis.

El **dashboard** se ordena por módulo y muestra a cada funcionario solo lo que su rol permite. La *Ficha clínica*
es exclusiva de roles clínicos que ingresan con ClaveÚnica. *Agenda* y *Derivaciones* corresponden al Módulo 3.
*Farmacia*, *Contacto* y *Simulador* corresponden al chatbot, y *Hospital*, *Indicadores* y *Satisfacción* a la
gestión. En el prototipo los registros clínicos, la dotación de box y los datos de camas, urgencias y
pabellones son **simulados**.
Detalle en [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) y relación con la postulación en
[docs/ALINEACION_FORMULACION.md](docs/ALINEACION_FORMULACION.md).

## Puesta en marcha

> Guía paso a paso para levantar todo en Windows con WhatsApp de Meta y ngrok:
> [docs/PUESTA_EN_MARCHA.md](docs/PUESTA_EN_MARCHA.md).

Requisitos: Docker 24+ con Docker Compose v2.

```bash
cp .env.example .env          # completa al menos POSTGRES_PASSWORD, DASHBOARD_PASSWORD, JWT_SECRET, ANALYTICS_SALT, INTERNAL_TOKEN
docker compose up -d --build  # la primera vez entrena el modelo Rasa dentro de la imagen (unos minutos)
docker compose ps             # todos los servicios deben quedar "healthy" / "running"
```

- **Dashboard:** http://localhost:8080. Los profesionales entran con *Ingresar con ClaveÚnica* (simulada en modo
  demo). La cuenta local `DASHBOARD_USER` / `DASHBOARD_PASSWORD` es solo de administración y no abre fichas.
- **Simulador:** pestaña *Simulador* del dashboard. Permite probar todos los flujos sin WhatsApp; esas
  conversaciones quedan con canal «Simulador» y se pueden excluir de los indicadores.
- **Sin credenciales de WhatsApp** el gateway arranca en modo `DRY_RUN`: procesa todo y registra los
  mensajes en el log en vez de enviarlos.

### Conectar WhatsApp con 360dialog

1. **Cuenta y número.** Regístrate en [360dialog](https://www.360dialog.com) y conecta un número que no esté
   usado en WhatsApp (el alta pide iniciar sesión con Facebook para crear la cuenta de WhatsApp Business;
   idealmente a nombre de la Universidad). En el *360dialog Hub* genera la **API key** del número.
2. **`.env`:**
   ```env
   D360_API_KEY=<api key del Hub>
   WEBHOOK_SECRET=<cadena aleatoria larga>
   ```
   y reinicia el gateway: `docker compose up -d whatsapp-gateway`.
3. **URL pública HTTPS.** 360dialog exige HTTPS con certificado válido. Con un servidor y dominio
   institucional, publica el puerto 8080 detrás de su proxy. Para probar desde tu PC, usa el túnel incluido:
   ```bash
   docker compose --profile tunel up -d tunel
   docker compose logs tunel          # copia la URL https://xxxx.trycloudflare.com
   ```
   (La URL del túnel cambia cada vez que se reinicia; para el piloto usa un dominio fijo.)
4. **Registrar el webhook:**
   ```bash
   docker compose exec whatsapp-gateway python -m app.register_webhook https://xxxx.trycloudflare.com/webhook
   ```
5. Escribe «hola» al número. En `docker compose logs -f whatsapp-gateway` debe aparecer
   «WhatsApp conectado vía 360dialog» al iniciar.

> Los recordatorios proactivos (tomas, horas, retiros) fuera de la ventana de 24 h de WhatsApp requieren
> **plantillas aprobadas**, que se gestionan desde el 360dialog Hub antes del piloto con pacientes.

Si prefieres la Cloud API de Meta directa, completa `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`,
`WHATSAPP_APP_SECRET` y `WHATSAPP_VERIFY_TOKEN` y registra `https://<dominio>/webhook` en Meta for Developers.

### Ingreso con ClaveÚnica

- **Profesionales:** botón «Ingresar con ClaveÚnica» del dashboard. Solo entran los RUN habilitados
  (variable `PROFESIONALES` o la API `/api/identidad/profesionales`), con su rol y sus establecimientos.
- **Pacientes:** cuando un trámite necesita identidad (resultados, derivaciones, modo cuidador), el chat envía
  un enlace de un solo uso a `PUBLIC_BASE_URL/id/vincular/...`, que debe ser la URL pública del sistema.
- **Modo demo** (`CLAVEUNICA_MODE=demo`, por defecto): un simulador reemplaza la página de ClaveÚnica y
  carga profesionales de prueba, como la Dra. Ana Rojas (médica en CESFAM Las Américas y HRT). El paciente
  de demostración con datos en dos establecimientos es el RUN **12.345.678-5**.
- **Producción:** `CLAVEUNICA_MODE=produccion`, `CLAVEUNICA_CLIENT_ID` y `CLAVEUNICA_CLIENT_SECRET`
  entregados por Gobierno Digital, y `https://<dominio>/id/callback` registrado como redirect URI.

### Modelo de lenguaje local (opcional)

El sistema funciona completo con reglas. Para sumar el modelo local (respaldo del NLU, apoyo diagnóstico y
orden del dictado):

```bash
docker compose --profile llm up -d ollama          # requiere GPU NVIDIA + nvidia-container-toolkit
docker compose exec ollama ollama pull qwen2.5:7b  # o el modelo que defina LLM_MODEL
```

Con `LLM_PROVIDER=ollama` (valor por defecto) ningún dato sale de la red. Un proveedor externo
(`anthropic`) queda bloqueado salvo `LLM_ALLOW_EXTERNAL=true`, y aun así nunca recibe datos clínicos.
Las salidas del modelo se validan: una hipótesis sin cita a un registro real se descarta, y un dictado
reordenado con texto que no estaba en la transcripción también se descarta.

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
pip install -e libs/medicai_common fastapi "uvicorn[standard]" sqlalchemy httpx redis PyJWT pyyaml pytest python-multipart tzdata
cd services/ms-agendamiento && uvicorn app.main:app --port 8101 --reload   # docs en /docs
cd dashboard && npm install && npm run dev                                  # proxy /api -> localhost:8080
```

## Estructura

```
libs/medicai_common/     system prompt, contrato de diálogo, mensajes, eventos, identidad, LLM local, utilidades
services/<servicio>/     app/ (código), tests/, Dockerfile, requirements.txt
services/nlu-rasa/       datos de entrenamiento, configuración y conjunto de prueba de Rasa
dashboard/               React + Vite
infra/                   nginx (API gateway) y bootstrap de PostgreSQL
scripts/                 simulación de conversaciones y evaluación del NLU
legacy/                  prototipo monolítico original (Flask), conservado como referencia
```
