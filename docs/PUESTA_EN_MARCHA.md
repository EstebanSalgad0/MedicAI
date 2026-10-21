# Puesta en marcha de MedicAI (Windows + WhatsApp de Meta + ngrok)

Guía para levantar el sistema completo en este computador cuando **todo ya está configurado**:
`.env` completo, app de Meta conectada a la cuenta de WhatsApp y ngrok vinculado a la cuenta.

Todos los comandos se ejecutan en **PowerShell**, desde la carpeta del proyecto:

```powershell
cd C:\Users\salga\OneDrive\Escritorio\Chatbot_MedicAI-main
```

---

## Resumen rápido

| # | Qué hacer | Comando / acción |
|---|---|---|
| 1 | Abrir Docker Desktop y esperar a que diga *Engine running* | (menú Inicio → Docker Desktop) |
| 2 | Levantar los 17 contenedores | `docker compose up -d` |
| 3 | Confirmar que todo está sano | `docker compose ps` |
| 4 | Abrir el túnel público (en otra terminal, dejarla abierta) | `ngrok http 8080` |
| 5 | Confirmar que la URL de ngrok es la misma registrada en Meta | ver [paso 4](#paso-4-abrir-el-túnel-de-ngrok) |
| 6 | Probar | Dashboard en http://localhost:8080 y «hola» por WhatsApp |

---

## Paso 1: Abrir Docker Desktop

Ábrelo desde el menú Inicio y espera a que el ícono de la ballena deje de moverse.
Para comprobar que está listo:

```powershell
docker info --format "{{.ServerVersion}}"
```

Debe mostrar un número de versión. Si da error, Docker todavía no terminó de arrancar.

## Paso 2: Levantar el sistema

```powershell
docker compose up -d
```

- La **primera vez**, o después de cambiar código, usa `docker compose up -d --build`. Tarda varios
  minutos porque construye las imágenes y entrena el modelo de Rasa.
- Las veces siguientes basta con `docker compose up -d`, que tarda segundos.

## Paso 3: Comprobar que todo está sano

```powershell
docker compose ps
```

Todos los servicios deben aparecer como `Up` y la mayoría como `(healthy)`. Rasa (`nlu-rasa`) tarda
unos 30 segundos en cargar su modelo; si aparece `(health: starting)`, espera y vuelve a consultar.

Comprobación de la conexión con WhatsApp:

```powershell
docker compose exec whatsapp-gateway python -c "import urllib.request;print(urllib.request.urlopen('http://localhost:8000/status').read().decode())"
```

Resultado esperado:

```json
{"provider":"meta","dry_run":false,"meta_signature_check":true,"shared_secret_check":false}
```

| Campo | Debe decir | Si no |
|---|---|---|
| `provider` | `meta` | Revisa `WHATSAPP_PROVIDER=meta` en el `.env` |
| `dry_run` | `false` | Falta `WHATSAPP_TOKEN` o `WHATSAPP_PHONE_NUMBER_ID`: el bot solo registra los mensajes, no los envía |
| `meta_signature_check` | `true` | Falta `WHATSAPP_APP_SECRET`: funciona, pero sin verificar que los mensajes vengan de Meta |

## Paso 4: Abrir el túnel de ngrok

Meta necesita una dirección pública con HTTPS para entregar los mensajes. ngrok la crea y la
redirige a tu computador. En **una terminal aparte**, que debe quedar abierta:

```powershell
ngrok http 8080
```

ngrok muestra una línea como esta:

```
Forwarding   https://xxxx-xxxx.ngrok-free.app -> http://localhost:8080
```

**Esa URL debe coincidir con la registrada en Meta.** Si cambió, actualízala:

1. Ve a [developers.facebook.com](https://developers.facebook.com) → tu app **MedicAI** →
   **WhatsApp → Configuración**.
2. En **Webhook**, presiona **Editar**.
3. URL de devolución de llamada: `https://<la-url-de-ngrok>/webhook`.
4. Token de verificación: el valor de `WHATSAPP_VERIFY_TOKEN` de tu `.env`.
5. **Verificar y guardar**, y comprueba que el campo **messages** siga suscrito.

> **Para que la URL no cambie:** en [dashboard.ngrok.com](https://dashboard.ngrok.com) → **Domains**,
> revisa el dominio fijo gratuito de tu cuenta y abre el túnel siempre con él:
> `ngrok http --url=<tu-dominio>.ngrok-free.app 8080`. Así no tendrás que tocar Meta nunca más.

Para ver las peticiones que llegan por el túnel, abre http://127.0.0.1:4040 en el navegador.

## Paso 5: Probar

- **Dashboard:** http://localhost:8080. Usuario y contraseña: `DASHBOARD_USER` y `DASHBOARD_PASSWORD` del `.env`.
- **WhatsApp:** escribe «hola» al número del bot. Debe reaccionar con 👀, mostrar «escribiendo…»
  y responder con el menú en pocos segundos.
- **Simulador:** pestaña *Simulador* del dashboard. Prueba los flujos sin pasar por WhatsApp.

---

## Token de Meta: evita que venza

El token que se copia desde **WhatsApp → Configuración de la API** es **temporal y dura 24 horas**.
Cuando vence, el bot recibe los mensajes pero **no puede responder**. En los logs aparece:

```
WhatsApp rechazó el mensaje (401): ... Session has expired ...
```

**Solución definitiva: token permanente de un usuario del sistema**

1. Entra a [business.facebook.com](https://business.facebook.com) → **Configuración del negocio**.
2. **Usuarios → Usuarios del sistema → Agregar**. Ponle un nombre (por ejemplo, `medicai-bot`) y el rol **Administrador**.
3. Con el usuario seleccionado: **Asignar activos** → **Apps** → *MedicAI* (control total) y
   **Cuentas de WhatsApp** → tu cuenta (control total).
4. **Generar token** → app *MedicAI* → caducidad **Nunca** → permisos
   `whatsapp_business_messaging` y `whatsapp_business_management`.
5. Copia el token en `WHATSAPP_TOKEN` del `.env` y aplica el cambio:

```powershell
docker compose up -d whatsapp-gateway
```

---

## Ajustes del Hospital Regional y del modo gestión

Variables del `.env` (ver `.env.example`):

| Variable | Para qué sirve |
|---|---|
| `HOSPITAL_DIRECCION`, `HOSPITAL_MESA_AYUDA`, `HOSPITAL_MESA_HORARIO`, `HOSPITAL_TELEFONO_UCI` | Datos que muestra el bot. **Verifícalos con el hospital**: la dirección aparece en la tarjeta de emergencia |
| `GESTION_USERS` | Números de WhatsApp que pueden usar el *modo gestión* (preguntar por camas, ausentismo, urgencias…), separados por coma |
| `GESTION_SIMULADOR` | `true` permite usar el modo gestión desde el simulador del dashboard |
| `GAP_OFFER_MINUTES` | Minutos que tiene un paciente para tomar un cupo liberado antes de que pase al siguiente |
| `REMINDER_LEAD_MINUTES` | Anticipación del aviso de cada toma de medicamento |
| `LIS_MODE` | `demo` = laboratorio simulado para resultados de exámenes |

Después de cambiarlas: `docker compose up -d`.

---

## Comandos del día a día

### Ver qué está pasando (logs)

```powershell
docker compose logs -f whatsapp-gateway              # mensajes que entran y salen de WhatsApp
docker compose logs -f orchestrator nlu              # cómo se interpretó cada mensaje
docker compose logs --since 10m                      # todo lo de los últimos 10 minutos
```

`Ctrl + C` deja de seguir los logs; los contenedores siguen funcionando.

### Después de cambiar el `.env`

```powershell
docker compose up -d                    # recrea solo los servicios afectados
docker compose up -d whatsapp-gateway   # o solo uno en particular
```

> ⚠️ `docker compose restart` **no** vuelve a leer el `.env`. Usa siempre `up -d`.

### Después de cambiar código

```powershell
docker compose up -d --build dashboard          # un servicio
docker compose up -d --build                    # todos
```

### Apagar

```powershell
docker compose stop      # detiene todo; al volver basta con "docker compose up -d"
docker compose down      # elimina los contenedores, pero conserva los datos
```

> ⛔ **Nunca uses `docker compose down -v`**: borra las bases de datos (horas, recordatorios,
> indicadores) y no se pueden recuperar.

Al terminar, cierra también la terminal de ngrok (`Ctrl + C`).

---

## Pruebas y datos de demostración

```powershell
# Conversaciones de prueba por el simulador (no envían nada a WhatsApp)
$env:PYTHONIOENCODING = "utf-8"
python scripts/simular_conversaciones.py --url http://localhost:8080 --user admin --password "<DASHBOARD_PASSWORD>" --repeticiones 1
```

Para mostrar el dashboard con 90 días de datos ficticios, y borrarlos después. Se usa `cmd /c` porque
PowerShell altera las tildes al pasar archivos con `<`:

```powershell
# Cargar
cmd /c "docker compose exec -T analytics python - analytics < scripts\cargar_datos_demo.py"
cmd /c "docker compose exec -T ms-agendamiento python - agendamiento < scripts\cargar_datos_demo.py"
cmd /c "docker compose exec -T ms-medicamentos python - medicamentos < scripts\cargar_datos_demo.py"

# Borrar (solo lo ficticio; los datos reales de WhatsApp no se tocan)
cmd /c "docker compose exec -T analytics python - analytics --borrar < scripts\cargar_datos_demo.py"
cmd /c "docker compose exec -T ms-agendamiento python - agendamiento --borrar < scripts\cargar_datos_demo.py"
cmd /c "docker compose exec -T ms-medicamentos python - medicamentos --borrar < scripts\cargar_datos_demo.py"
```

---

## Problemas frecuentes

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| El bot no responde y en http://127.0.0.1:4040 no aparece ningún `POST /webhook` | ngrok cerrado, URL distinta a la de Meta o campo *messages* sin suscribir | Revisa el [paso 4](#paso-4-abrir-el-túnel-de-ngrok) |
| Llega `POST /webhook` con respuesta `401` | `WHATSAPP_APP_SECRET` incorrecto | Copia la **Clave secreta de la app** (32 caracteres) desde *Configuración de la app → Básica* y ejecuta `docker compose up -d whatsapp-gateway` |
| Llega `POST /webhook 200`, pero no hay respuesta y el log dice `WhatsApp rechazó el mensaje (401)` | Token vencido | [Token permanente](#token-de-meta-evita-que-venza) |
| El log dice `WhatsApp rechazó el mensaje` con `131030` | Con el número de prueba, tu teléfono no está en la lista de destinatarios | Agrégalo en *WhatsApp → Configuración de la API → Para* |
| `/status` muestra `dry_run: true` | Faltan credenciales en el `.env` o no se aplicaron | Completa el `.env` y ejecuta `docker compose up -d whatsapp-gateway` |
| El bot responde «⚠️ Tuve un problema técnico» | Un servicio interno falló | `docker compose ps` para ver cuál no está sano y `docker compose logs <servicio>` |
| El dashboard no carga | El contenedor `gateway` o `dashboard` no está arriba | `docker compose up -d gateway dashboard` |
| `port is already allocated` al levantar | Otro programa usa el puerto 8080 | Cierra ese programa o define `HTTP_PORT=8081` en el `.env` y usa `ngrok http 8081` |
| Meta verifica el webhook, pero los mensajes nunca llegan | La cuenta de WhatsApp no está conectada a la app | Ejecuta el comando de abajo con el *Identificador de la cuenta de WhatsApp Business* |

Conectar la cuenta de WhatsApp con la app (solo se hace una vez; ya está hecho en esta instalación):

```powershell
docker compose exec whatsapp-gateway python -c "import os,urllib.request as u;r=u.Request('https://graph.facebook.com/'+os.environ['WHATSAPP_API_VERSION']+'/<WABA_ID>/subscribed_apps',data=b'',method='POST',headers={'Authorization':'Bearer '+os.environ['WHATSAPP_TOKEN']});print(u.urlopen(r).read().decode())"
```

Debe responder `{"success":true}`.
