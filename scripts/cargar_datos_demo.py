#!/usr/bin/env python3
"""Carga datos de demostración para recorrer el sistema completo.

Genera ~90 días de actividad ficticia (conversaciones, trámites, encuestas,
adherencia a tomas), horas agendadas pasadas y futuras, y retiros de farmacia.
Se ejecuta dentro de cada contenedor para usar los mismos modelos y la misma
seudonimización que el sistema real.

Los datos quedan marcados para poder borrarlos sin tocar datos reales:
  - pacientes con teléfonos ficticios que empiezan con 5699000
  - eventos de analítica con props.demo = true
Volver a ejecutarlo reemplaza la carga anterior (no duplica).

Uso, desde la raíz del repositorio y con el sistema levantado:
    docker compose exec -T analytics       python - analytics    < scripts/cargar_datos_demo.py
    docker compose exec -T ms-agendamiento python - agendamiento < scripts/cargar_datos_demo.py
    docker compose exec -T ms-medicamentos python - medicamentos < scripts/cargar_datos_demo.py
Para borrar solo los datos de demostración, agrega --borrar al final de cada comando.
"""
from __future__ import annotations

import random
import sys
import uuid
from datetime import date, datetime, time, timedelta, timezone

from medicai_common.textutil import TZ

DEMO_PREFIX = "5699000"
DAYS = 90
CENTERS = ["las_americas", "julio_contardo", "curico_centro", "san_juan_de_dios", "armando_williams"]
CENTER_W = [30, 22, 20, 16, 12]
rng = random.Random(2026)

NOMBRES = ["María", "José", "Juan", "Ana", "Luis", "Carmen", "Pedro", "Rosa", "Jorge", "Patricia", "Manuel",
           "Isabel", "Carlos", "Gloria", "Francisco", "Teresa", "Sergio", "Marta", "Héctor", "Verónica",
           "Camila", "Matías", "Valentina", "Benjamín", "Javiera", "Ignacio", "Fernanda", "Cristián"]
APELLIDOS = ["González", "Muñoz", "Rojas", "Díaz", "Pérez", "Soto", "Contreras", "Silva", "Martínez", "Sepúlveda",
             "Morales", "Rodríguez", "López", "Fuentes", "Hernández", "Torres", "Araya", "Flores", "Espinoza",
             "Valenzuela", "Castillo", "Tapia", "Reyes", "Gutiérrez", "Castro", "Pizarro", "Álvarez", "Vásquez"]


def phone(i: int) -> str:
    return f"{DEMO_PREFIX}{i:04d}"


def full_name() -> str:
    return f"{rng.choice(NOMBRES)} {rng.choice(APELLIDOS)} {rng.choice(APELLIDOS)}"


def pick(weights: dict):
    return rng.choices(list(weights), weights=list(weights.values()))[0]


def to_utc(local: datetime) -> datetime:
    return local.replace(tzinfo=TZ).astimezone(timezone.utc).replace(tzinfo=None)


def today_local() -> date:
    return datetime.now(TZ).date()


def workdays(start: date, end: date):
    d = start
    while d <= end:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


# ----------------------------------------------------------------- analytics

def seed_analytics(borrar: bool) -> None:
    from sqlalchemy import delete, select

    from app.main import pseudonym
    from app.models import Event, SessionLocal, init_db

    init_db()
    with SessionLocal() as db:
        ids = [i for i, p in db.execute(select(Event.id, Event.props)) if (p or {}).get("demo")]
        for k in range(0, len(ids), 5000):
            db.execute(delete(Event).where(Event.id.in_(ids[k:k + 5000])))
        db.commit()
    print(f"analytics: {len(ids)} eventos de demostración eliminados")
    if borrar:
        return

    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    rows: list[Event] = []

    def ev(ts, type_, service, uid=None, channel=None, center=None, **props):
        if ts > now_utc:
            return
        props["demo"] = True
        rows.append(Event(ts=ts, type=type_, service=service, user_hash=pseudonym(uid), center=center,
                          channel=channel or ("web" if (uid or "").startswith("web:") else "whatsapp"),
                          props=props))

    def latency(src: str | None) -> tuple[float, float | None]:
        if src is None:  # botón: no pasa por el NLU
            return round(rng.lognormvariate(5.4, 0.35), 1), None
        nlu_ms = {"rasa": rng.lognormvariate(5.6, 0.3), "llm": rng.lognormvariate(7.4, 0.3),
                  "rules": rng.lognormvariate(3.5, 0.3), "fallback": rng.lognormvariate(7.5, 0.25),
                  "safety": 2.0}[src]
        return round(nlu_ms + rng.lognormvariate(5.3, 0.4), 1), round(nlu_ms, 1)

    def interaction(ts, uid, service, input_, intent=None, src=None, **extra):
        lat, nlu_lat = latency(src if input_ == "text" else None)
        conf = None
        if input_ == "text":
            conf = {"rasa": rng.uniform(0.72, 0.99), "llm": rng.uniform(0.7, 0.92), "rules": 0.6,
                    "fallback": rng.uniform(0.1, 0.4), "safety": 1.0}[src]
            conf = round(conf, 3)
        ev(ts, "interaction", service, uid, interaction_id=uuid.uuid4().hex[:12], latency_ms=lat, input=input_,
           intent=intent if input_ == "text" else None, confidence=conf,
           nlu_source=src if input_ == "text" else None, nlu_latency_ms=nlu_lat,
           fallback=extra.get("fallback", False), human_handoff_offered=extra.get("handoff_offered", False),
           red_flag=extra.get("red_flag"), resolved=extra.get("resolved", False),
           survey_sent=extra.get("survey_sent", False), handoff=False, error=None)
        if not uid.startswith("web:"):
            ev(ts + timedelta(seconds=1), "delivery", "whatsapp-gateway", uid,
               end_to_end_ms=round(lat + rng.lognormvariate(6.6, 0.4), 1))

    def quick_answer(ts, uid, service):
        """Respuesta de un toque a un aviso (toma, asistencia, retiro). El orquestador la
        registra como un trámite de un turno que se inicia y se resuelve en el mismo mensaje."""
        interaction(ts, uid, service, "option", resolved=True)
        ev(ts, "flow_started", service, uid, via="option")
        ev(ts, "flow_completed", service, uid, resolved=True, turns=1, duration_s=0.0)

    SERVICES = {"agendamiento": 30, "recordatorios": 18, "orientacion": 22, "medicamentos": 18, "derivacion": 12}
    START = {"agendamiento": ("agendar_cita", 4, 6), "recordatorios": ("recordatorio_medicamento", 3, 5),
             "orientacion": ("orientacion_sintomas", 3, 4), "medicamentos": ("farmacia", 5, 7),
             "derivacion": ("guia_ruta", 2, 3)}
    ALT = {"agendamiento": "ver_citas", "recordatorios": "ver_recordatorios", "medicamentos": "ver_retiros"}
    patients = [phone(i) for i in range(1, 321)]
    reminder_users: dict[str, int] = {}  # paciente -> tomas por día
    pickup_users: list[str] = []
    start_day = today_local() - timedelta(days=DAYS - 1)

    for d in range(DAYS):
        day = start_day + timedelta(days=d)
        growth = 4 + 20 * (d / DAYS) ** 0.8          # piloto que va creciendo
        n_sessions = max(1, int(rng.gauss(growth, growth * 0.2) * (0.45 if day.weekday() >= 5 else 1)))
        slow_day = rng.random() < 0.06                # algún día con el LLM lento

        for _ in range(n_sessions):
            web = rng.random() < 0.12
            uid = f"web:demo-{uuid.uuid4().hex[:8]}" if web else rng.choice(patients)
            hour = rng.choices(range(8, 23), weights=[4, 8, 10, 10, 9, 7, 6, 7, 8, 8, 7, 6, 5, 3, 2])[0]
            t = to_utc(datetime.combine(day, time(hour, rng.randrange(60), rng.randrange(60))))
            step = lambda: timedelta(seconds=rng.randint(8, 45))  # noqa: E731

            if rng.random() < 0.3:
                interaction(t, uid, "orchestrator", "text", "saludo", "rasa")
                t += step()

            r = rng.random()
            if r < 0.015:  # alerta de urgencia detectada en el texto
                flag = "salud_mental" if rng.random() < 0.3 else "urgencia"
                interaction(t, uid, "orchestrator", "text", "emergencia", "safety", red_flag=flag)
                continue
            if r < 0.055:  # mensaje no entendido
                interaction(t, uid, "orchestrator", "text", "nlu_fallback", "fallback", fallback=True)
                t += step()
                if rng.random() < 0.3:
                    interaction(t, uid, "orchestrator", "text", "nlu_fallback", "fallback", fallback=True,
                                handoff_offered=True)
                    continue

            svc = pick(SERVICES)
            intent, lo, hi = START[svc]
            if svc in ALT and rng.random() < 0.15:
                intent, lo, hi = ALT[svc], 1, 2
            via_menu = rng.random() < 0.25
            src = pick({"rasa": 82, "llm": 13, "rules": 5})
            if slow_day and src == "rasa" and rng.random() < 0.5:
                src = "llm"
            if via_menu:
                interaction(t, uid, svc, "option")
            else:
                interaction(t, uid, svc, "text", intent, src)
            ev(t, "flow_started", svc, uid, via="option" if via_menu else "nlu")
            t0, turns = t, rng.randint(lo, hi)
            for _ in range(turns - 2):
                t += step()
                interaction(t, uid, svc, "option" if rng.random() < 0.7 else "flow_text")

            outcome = rng.random()
            if outcome > 0.93:  # abandona a medio camino
                ev(t + timedelta(minutes=30), "flow_abandoned", svc, uid, reason="timeout", turns=turns - 1)
                continue
            t += step()
            resolved = outcome < 0.88
            survey = resolved and rng.random() < 0.45
            interaction(t, uid, svc, "option", resolved=resolved, survey_sent=survey)
            ev(t, "flow_completed", svc, uid, resolved=resolved, turns=turns,
               duration_s=round((t - t0).total_seconds(), 1))

            if resolved:
                center = rng.choices(CENTERS, weights=CENTER_W)[0]
                if svc == "agendamiento" and intent == "agendar_cita":
                    lead = rng.randint(1, 10)
                    ev(t, "appointment_booked", svc, uid, center=center, appointment_id=None,
                       prestacion=rng.choice(["medicina_general", "control_cronico", "matrona", "enfermeria",
                                              "odontologia", "nino_sano", "salud_mental", "kinesiologia"]),
                       lead_days=lead, rescheduled=rng.random() < 0.06)
                    slot = t + timedelta(days=lead)
                    if rng.random() < 0.65:
                        quick_answer(slot - timedelta(hours=16), uid, svc)
                        ev(slot - timedelta(hours=16), "attendance_confirmed", svc, uid, center=center)
                    a = rng.random()
                    if a < 0.07:
                        ev(slot - timedelta(hours=15), "appointment_cancelled", svc, uid, center=center)
                    elif a < 0.86:
                        ev(slot + timedelta(hours=3), "appointment_attended", svc, uid, center=center)
                    else:
                        ev(slot + timedelta(hours=3), "appointment_no_show", svc, uid, center=center)
                elif svc == "agendamiento" and rng.random() < 0.3:
                    ev(t, "appointment_cancelled", svc, uid, center=center)
                elif svc == "recordatorios" and intent == "recordatorio_medicamento":
                    doses = pick({1: 55, 2: 35, 3: 10})
                    ev(t, "reminder_created", svc, uid, doses_per_day=doses, source="chat", updated=False)
                    if not web:
                        reminder_users.setdefault(uid, doses)
                elif svc == "orientacion":
                    nivel = pick({"autocuidado": 40, "control": 35, "prioritario": 18, "urgencia": 7})
                    ev(t, "triage_completed", svc, uid,
                       categoria=rng.choice(["respiratorio", "digestivo", "dolor", "piel", "fiebre", "general"]),
                       nivel=nivel, sintomas_detectados=rng.randint(1, 5), regla_aplicada=rng.random() < 0.6)
                    if nivel == "urgencia" and rng.random() < 0.4:
                        ev(t, "red_flag_detected", svc, uid, tipo="urgencia", origen="orientacion")
                elif svc == "medicamentos" and intent == "farmacia":
                    status = pick({"available": 70, "low": 18, "none": 12})
                    ev(t, "stock_checked", svc, uid, center=center, status=status)
                    if rng.random() < 0.7:
                        ev(t, "pickup_scheduled", svc, uid, center=center, freq_days=pick({30: 75, None: 25}),
                           stock_status=status)
                        if not web:
                            pickup_users.append(uid)
                    elif status == "none":
                        ev(t, "stock_alert_subscribed", svc, uid, center=center)
                elif svc == "derivacion":
                    ev(t, "referral_guided", svc, uid,
                       doc_type=pick({"interconsulta": 40, "examenes": 30, "receta": 15, "urgente": 8, "otro": 7}),
                       ges=pick({"si": 30, "no": 60, None: 10}))
            if survey and rng.random() < 0.7:
                t += timedelta(minutes=rng.randint(1, 20))
                interaction(t, uid, "orchestrator", "option")
                ev(t, "survey_response", "orchestrator", uid,
                   rating=pick({5: 52, 4: 30, 3: 10, 2: 5, 1: 3}))

        # respuestas a recordatorios de tomas de quienes ya los tienen activos
        for uid, doses in list(reminder_users.items()):
            for h in [8, 14, 21][:doses]:
                t = to_utc(datetime.combine(day, time(h, rng.randrange(0, 50))))
                ev(t, "dose_reminder_sent", "recordatorios", uid)
                ans = pick({"taken": 72, "skipped": 9, "expired": 15, "snoozed": 4})
                if ans == "expired":
                    ev(t + timedelta(hours=2), "dose_expired", "recordatorios", uid)
                    continue
                delay = rng.randint(1, 50)
                t += timedelta(minutes=delay)
                quick_answer(t, uid, "recordatorios")
                ev(t, f"dose_{ans}", "recordatorios", uid, response_delay_min=delay)

        # retiros de farmacia que vencen ese día (~30 días después de programarlos)
        if d >= 30 and pickup_users:
            for uid in rng.sample(pickup_users, k=min(len(pickup_users), rng.randint(0, 3))):
                t = to_utc(datetime.combine(day, time(rng.randint(9, 18), rng.randrange(60))))
                center = rng.choices(CENTERS, weights=CENTER_W)[0]
                done = rng.random() < 0.82
                if done or rng.random() < 0.5:  # algunos no retiros se cierran solos a los 7 días, sin respuesta
                    quick_answer(t, uid, "medicamentos")
                ev(t,"pickup_done" if done else "pickup_missed", "medicamentos", uid, center=center)

    with SessionLocal() as db:
        db.add_all(rows)
        db.commit()
    print(f"analytics: {len(rows)} eventos de demostración cargados ({DAYS} días)")


# -------------------------------------------------------------- agendamiento

def seed_agendamiento(borrar: bool) -> None:
    from sqlalchemy import delete

    from app.catalog import HORARIOS
    from app.models import Appointment, SessionLocal, init_db

    init_db()
    with SessionLocal() as db:
        n = db.execute(delete(Appointment).where(Appointment.user_id.like(f"{DEMO_PREFIX}%"))).rowcount
        db.commit()
    print(f"agendamiento: {n} horas de demostración eliminadas")
    if borrar:
        return

    PREST = {"medicina_general": 30, "control_cronico": 20, "matrona": 10, "enfermeria": 10, "odontologia": 9,
             "nino_sano": 7, "salud_mental": 5, "kinesiologia": 4, "nutricion": 3, "toma_muestras": 2}
    now = datetime.now(TZ).replace(tzinfo=None)
    today = now.date()
    rows = []
    for i, day in enumerate(workdays(today - timedelta(days=30), today + timedelta(days=14))):
        for _ in range(rng.randint(3, 8)):
            slot = datetime.combine(day, time.fromisoformat(rng.choice(HORARIOS)))
            past = slot < now
            reply = None
            if past and (today - day).days <= 1:
                status = pick({"confirmed": 70, "attended": 20, "no_show": 10})  # falta registrar asistencia
            elif past:
                status = pick({"attended": 80, "no_show": 13, "cancelled": 7})
            else:
                status = pick({"confirmed": 92, "cancelled": 8})
            if status == "cancelled":
                reply = "cancel" if rng.random() < 0.6 else None
            elif past or (day - today).days <= 1:
                reply = pick({"yes": 60, "reschedule": 5, None: 35})
            lead = rng.randint(1, 10)
            rows.append(Appointment(
                user_id=phone(rng.randint(1, 320)), patient_name=full_name(),
                channel="web" if rng.random() < 0.08 else "whatsapp", prestacion=pick(PREST),
                center_id=rng.choices(CENTERS, weights=CENTER_W)[0], slot_at=slot, status=status,
                reminder_sent=True, attendance_reply=reply,
                created_at=min(slot - timedelta(days=lead, hours=rng.randint(0, 8)), now)))
    with SessionLocal() as db:
        db.add_all(rows)
        db.commit()
    print(f"agendamiento: {len(rows)} horas de demostración cargadas")


# -------------------------------------------------------------- medicamentos

def seed_medicamentos(borrar: bool) -> None:
    from sqlalchemy import delete, select

    from app.models import Pickup, SessionLocal, StockAlert, StockItem, init_db

    init_db()
    with SessionLocal() as db:
        n = db.execute(delete(Pickup).where(Pickup.user_id.like(f"{DEMO_PREFIX}%"))).rowcount
        n += db.execute(delete(StockAlert).where(StockAlert.user_id.like(f"{DEMO_PREFIX}%"))).rowcount
        db.commit()
    print(f"medicamentos: {n} retiros/avisos de demostración eliminados")
    if borrar:
        return

    today = today_local()
    with SessionLocal() as db:
        stock = list(db.scalars(select(StockItem)))
    if not stock:
        print("medicamentos: no hay inventario; activa SEED_DEMO_STOCK=true o carga stock desde el dashboard")
        return
    usual = [s for s in stock if s.stock > 0] or stock
    rows = []

    def pickup(due: date, status: str):
        s = rng.choice(usual)
        rows.append(Pickup(user_id=phone(rng.randint(1, 320)), medication=s.name, center_id=s.center_id,
                           due_date=due, hour=rng.choice(["09:00", "10:00", "11:00", "15:00"]),
                           freq_days=pick({30: 80, None: 20}), status=status,
                           notified_before=True, notified_day=due <= today))

    for _ in range(55):
        due = today - timedelta(days=rng.randint(1, 60))
        pickup(due, "done" if rng.random() < 0.85 else "missed")
    for _ in range(6):
        pickup(today - timedelta(days=rng.randint(1, 5)), "pending")   # vencidos sin respuesta aún
    for _ in range(34):
        pickup(today + timedelta(days=rng.randint(0, 30)), "pending")

    agotados = [s for s in stock if s.stock <= 0] or stock[:3]
    for i in range(9):
        s = rng.choice(agotados)
        rows.append(StockAlert(user_id=phone(rng.randint(1, 320)), center_id=s.center_id, key=s.key,
                               name=s.name, notified=i >= 7))
    with SessionLocal() as db:
        db.add_all(rows)
        db.commit()
    print(f"medicamentos: {len(rows)} retiros y avisos de stock de demostración cargados")


if __name__ == "__main__":
    args = sys.argv[1:]
    target = next((a for a in args if not a.startswith("-")), "")
    fn = {"analytics": seed_analytics, "agendamiento": seed_agendamiento, "medicamentos": seed_medicamentos}.get(target)
    if not fn:
        sys.exit("Indica qué cargar: analytics | agendamiento | medicamentos  (y --borrar para eliminar)")
    fn("--borrar" in args)
