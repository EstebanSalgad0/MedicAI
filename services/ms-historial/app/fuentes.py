"""Fuentes de datos clínicos: una por establecimiento de la red.

Cada establecimiento tiene sus propios registros. MedicAI los consulta en paralelo y cada
dato conserva su origen (establecimiento, expediente, fecha y sección) para citarlo.

FUENTES_MODE:
  demo  registros simulados, reproducibles por RUN (incluye un caso de demostración completo:
        RUN 12.345.678-5 con datos en CESFAM Las Américas y en el Hospital Regional).
  fhir  adaptador de referencia a servidores HL7 FHIR R4 por establecimiento
        (FHIR_URLS="las_americas=https://...,hrt=https://..."). Validar el mapeo con cada
        sistema antes de usarlo con pacientes.
"""
from __future__ import annotations

import hashlib
import logging
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Iterator

import httpx

from medicai_common.centros import CENTROS, ESTABLECIMIENTOS
from medicai_common.textutil import today_local

log = logging.getLogger("historial.fuentes")

TIPO_EST = {k: ("Hospital" if k == "hrt" else "CESFAM") for k, _, _ in ESTABLECIMIENTOS}
NIVEL_EST = {k: ("Atención terciaria" if k == "hrt" else "Atención primaria") for k, _, _ in ESTABLECIMIENTOS}
NOMBRE_EST = {k: n for k, n, _ in ESTABLECIMIENTOS}
TIMEOUT_S = float(os.getenv("FUENTE_TIMEOUT_SECONDS", "4"))


@dataclass
class Cita:
    establecimiento_id: str
    expediente: str
    fecha: date
    seccion: str
    pagina: int | None = None

    @property
    def establecimiento(self) -> str:
        return NOMBRE_EST.get(self.establecimiento_id, self.establecimiento_id)

    def texto(self) -> str:
        pag = f", p. {self.pagina}" if self.pagina else ""
        return f"[{self.establecimiento} · Exp. {self.expediente} · {self.fecha:%d-%m-%Y} · {self.seccion}{pag}]"

    def dict(self) -> dict:
        return {"establecimiento_id": self.establecimiento_id, "establecimiento": self.establecimiento,
                "expediente": self.expediente, "fecha": self.fecha.isoformat(), "seccion": self.seccion,
                "pagina": self.pagina, "texto": self.texto()}


@dataclass
class Registro:
    """Un dato clínico tal como está en la fuente. `detalle` depende del tipo:
    medicamento {dosis, vigente_hasta}; examen {valor, unidad, ref_min, ref_max, area, informe};
    control {programado, estado, prestacion}; condicion {desde}; alergia {reaccion}."""

    id: str
    tipo: str  # condicion | antecedente | medicamento | alergia | examen | control | consulta
    nombre: str
    cita: Cita
    detalle: dict = field(default_factory=dict)

    def dict(self) -> dict:
        d = {k: (v.isoformat() if isinstance(v, date) else v) for k, v in self.detalle.items()}
        return {"id": self.id, "tipo": self.tipo, "nombre": self.nombre, "detalle": d, "cita": self.cita.dict()}


@dataclass
class Paciente:
    nombre: str
    nacimiento: date | None
    sexo: str | None
    inscripcion: str | None  # establecimiento de inscripción (APS)


@dataclass
class Resultado:
    establecimiento_id: str
    estado: str  # ok | sin_registros | error | tiempo_agotado
    ms: float
    paciente: Paciente | None = None
    registros: list[Registro] = field(default_factory=list)
    error: str | None = None

    def resumen(self) -> dict:
        return {"id": self.establecimiento_id, "nombre": NOMBRE_EST.get(self.establecimiento_id),
                "tipo": TIPO_EST.get(self.establecimiento_id), "nivel": NIVEL_EST.get(self.establecimiento_id),
                "estado": self.estado, "ms": round(self.ms), "registros": len(self.registros), "error": self.error}


# ======================= modo demo =======================

EXAMENES = {  # nombre: (unidad, ref_min, ref_max, área)
    "Hemoglobina glicosilada (HbA1c)": ("%", 4.0, 6.0, "Laboratorio"),
    "Glicemia en ayunas": ("mg/dL", 70, 100, "Laboratorio"),
    "Creatinina plasmática": ("mg/dL", 0.7, 1.3, "Laboratorio"),
    "VFG estimada": ("mL/min/1,73 m²", 60, None, "Laboratorio"),
    "Potasio plasmático": ("mEq/L", 3.5, 5.1, "Laboratorio"),
    "Colesterol LDL": ("mg/dL", None, 100, "Laboratorio"),
    "TSH": ("µUI/mL", 0.4, 4.0, "Laboratorio"),
    "Hemoglobina": ("g/dL", 12.0, 16.0, "Laboratorio"),
    "Razón albúmina/creatinina en orina": ("mg/g", None, 30, "Laboratorio"),
}
MEDS = {  # condición: [(medicamento, dosis)]
    "Hipertensión arterial": [("Losartán 50 mg", "1 comprimido cada 12 horas")],
    "Diabetes mellitus tipo 2": [("Metformina 850 mg", "1 comprimido cada 12 horas con comidas")],
    "Dislipidemia": [("Atorvastatina 20 mg", "1 comprimido en la noche")],
    "Hipotiroidismo": [("Levotiroxina 75 mcg", "1 comprimido en ayunas")],
    "Asma bronquial": [("Salbutamol inhalador 100 mcg", "2 inhalaciones si presenta síntomas")],
}
EXAMENES_POR_COND = {
    "Hipertensión arterial": ["Creatinina plasmática", "VFG estimada", "Potasio plasmático"],
    "Diabetes mellitus tipo 2": ["Hemoglobina glicosilada (HbA1c)", "Glicemia en ayunas",
                                 "Razón albúmina/creatinina en orina"],
    "Dislipidemia": ["Colesterol LDL"],
    "Hipotiroidismo": ["TSH"],
}
NOMBRES_F = ["María", "Rosa", "Carmen", "Ana", "Patricia", "Javiera", "Camila", "Isabel"]
NOMBRES_M = ["José", "Luis", "Pedro", "Manuel", "Carlos", "Diego", "Matías", "Sergio"]
APELLIDOS = ["González", "Muñoz", "Rojas", "Díaz", "Pérez", "Soto", "Contreras", "Silva", "Morales", "Fuentes"]
CASO_DEMO = "12345678-5"


def _rng(*partes: str) -> random.Random:
    return random.Random(int(hashlib.sha256(":".join(partes).encode()).hexdigest(), 16))


def _expediente(run: str, est: str) -> str:
    return f"{int(hashlib.sha256(f'{run}:{est}'.encode()).hexdigest(), 16) % 900000 + 100000}"


class _Builder:
    """Arma los registros de un paciente simulado, todos con su cita."""

    def __init__(self, run: str):
        self.run, self.items, self.n = run, [], 0

    def add(self, est: str, tipo: str, nombre: str, fecha: date, seccion: str, pagina: int | None = None,
            **detalle) -> None:
        self.n += 1
        cita = Cita(est, _expediente(self.run, est), fecha, seccion, pagina)
        self.items.append(Registro(f"R{self.n}", tipo, nombre, cita, detalle))

    def examen(self, est: str, nombre: str, valor: float, fecha: date, pagina: int = 1, informe: str | None = None):
        unidad, lo, hi, area = EXAMENES[nombre]
        self.add(est, "examen", nombre, fecha, area, pagina, valor=valor, unidad=unidad, ref_min=lo, ref_max=hi,
                 area=area, informe=informe)


def _caso_demo(hoy: date) -> tuple[Paciente, list[Registro]]:
    """Caso de demostración: paciente crónico atendido en APS y en el hospital. Muestra lo que
    se pierde sin consulta multi-establecimiento: la alergia y dos fármacos están solo en el HRT."""
    d = lambda dias: hoy - timedelta(days=dias)  # noqa: E731
    b, aps, hrt = _Builder(CASO_DEMO), "las_americas", "hrt"
    b.add(aps, "condicion", "Hipertensión arterial", d(2900), "Problemas de salud (PSCV)", 1, desde=d(2900))
    b.add(aps, "condicion", "Diabetes mellitus tipo 2", d(2200), "Problemas de salud (PSCV)", 1, desde=d(2200))
    b.add(aps, "condicion", "Enfermedad renal crónica etapa 3a", d(400), "Problemas de salud (PSCV)", 1, desde=d(400))
    b.add(aps, "condicion", "Dislipidemia", d(2200), "Problemas de salud (PSCV)", 1, desde=d(2200))
    b.add(aps, "antecedente", "Colecistectomía (2015)", d(3900), "Antecedentes quirúrgicos", 2)
    b.add(aps, "antecedente", "Exfumador (suspendió en 2018)", d(2900), "Hábitos", 2)
    for med, dosis in [("Losartán 50 mg", "1 comprimido cada 12 horas"),
                       ("Metformina 850 mg", "1 comprimido cada 12 horas con comidas"),
                       ("Atorvastatina 20 mg", "1 comprimido en la noche"),
                       ("Ácido acetilsalicílico 100 mg", "1 comprimido al día")]:
        b.add(aps, "medicamento", med, d(225), "Receta crónica PSCV", 3, dosis=dosis, vigente_hasta=hoy + timedelta(days=140))
    b.examen(aps, "Hemoglobina glicosilada (HbA1c)", 8.1, d(250), 4)
    b.examen(aps, "Hemoglobina glicosilada (HbA1c)", 9.4, d(60), 4)
    b.examen(aps, "Glicemia en ayunas", 182, d(60), 4)
    b.examen(aps, "Creatinina plasmática", 1.5, d(60), 4)
    b.examen(aps, "VFG estimada", 44, d(60), 4)
    b.examen(aps, "Potasio plasmático", 5.3, d(60), 4)
    b.examen(aps, "Colesterol LDL", 128, d(60), 5)
    b.examen(aps, "Razón albúmina/creatinina en orina", 85, d(60), 5)
    b.add(aps, "consulta", "Control PSCV (médico)", d(225), "Registro de atención", 6,
          resumen="Control cardiovascular. Se indica continuar tratamiento y control en 6 meses.")
    b.add(aps, "control", "Control PSCV", d(225), "Agenda de controles", 6, programado=d(43), estado="pendiente",
          prestacion="control_cronico")
    b.add(aps, "control", "Vacuna influenza (campaña)", d(150), "Programa Nacional de Inmunizaciones", 7,
          programado=d(30), estado="pendiente", prestacion="vacunacion")
    b.add(hrt, "alergia", "Penicilina", d(1400), "Alergias (hoja de ingreso)", 1, reaccion="Urticaria generalizada")
    b.add(hrt, "consulta", "Cardiología (interconsulta)", d(120), "Policlínico de Cardiología", 2,
          resumen="Evaluación por disnea de esfuerzo. Ecocardiograma solicitado. Se agrega espironolactona.")
    b.examen(hrt, "Potasio plasmático", 5.0, d(120), 3)
    b.add(hrt, "examen", "Ecocardiograma transtorácico", d(110), "Imagenología", 4, valor=None, unidad=None,
          ref_min=None, ref_max=None, area="Imagenología",
          informe="FEVI 45 %. Hipertrofia concéntrica leve del ventrículo izquierdo.")
    b.add(hrt, "medicamento", "Espironolactona 25 mg", d(120), "Receta (Cardiología)", 2, dosis="1 comprimido al día",
          vigente_hasta=hoy + timedelta(days=60))
    b.add(hrt, "consulta", "Urgencia adultos", d(8), "Dato de atención de urgencia (DAU)", 1,
          resumen="Consulta por lumbago mecánico. Alta con analgesia.")
    b.add(hrt, "medicamento", "Ibuprofeno 400 mg", d(8), "Receta de urgencia (DAU)", 1,
          dosis="1 comprimido cada 8 horas por 10 días", vigente_hasta=d(-2))
    return Paciente("Juan Pérez Soto", date(hoy.year - 67, 4, 12), "M", aps), b.items


def _caso_generico(run: str, hoy: date) -> tuple[Paciente, list[Registro]]:
    rng = _rng(run)
    sexo = rng.choice("FM")
    edad = rng.randint(1, 88)
    nombre = f"{rng.choice(NOMBRES_F if sexo == 'F' else NOMBRES_M)} {rng.choice(APELLIDOS)} {rng.choice(APELLIDOS)}"
    aps = rng.choice(CENTROS)[0]
    b = _Builder(run)
    d = lambda dias: hoy - timedelta(days=dias)  # noqa: E731
    conds = []
    if edad >= 35:
        prob = {"Hipertensión arterial": .5 if edad >= 55 else .2, "Diabetes mellitus tipo 2": .25,
                "Dislipidemia": .3, "Hipotiroidismo": .14 if sexo == "F" else .04}
        conds = [c for c, p in prob.items() if rng.random() < p]
    if rng.random() < .08:
        conds.append("Asma bronquial")
    for c in conds:
        desde = d(rng.randint(400, 3600))
        b.add(aps, "condicion", c, desde, "Problemas de salud", 1, desde=desde)
        for med, dosis in MEDS.get(c, []):
            b.add(aps, "medicamento", med, d(rng.randint(20, 160)), "Receta crónica", 3, dosis=dosis,
                  vigente_hasta=hoy + timedelta(days=rng.randint(15, 160)))
        for ex in EXAMENES_POR_COND.get(c, []):
            unidad, lo, hi, _ = EXAMENES[ex]
            base = (lo + hi) / 2 if lo is not None and hi is not None else (hi * .8 if hi else lo * 1.4)
            for dias in sorted(rng.sample(range(30, 400), 2), reverse=True):
                fuera = rng.random() < .35
                factor = rng.uniform(1.15, 1.5) if fuera else rng.uniform(.85, 1.1)
                if ex == "VFG estimada":
                    factor = rng.uniform(.55, .9) if fuera else rng.uniform(1.0, 1.5)
                b.examen(aps, ex, round(base * factor, 1), d(dias), 4)
    cronico = any(c in conds for c in ("Hipertensión arterial", "Diabetes mellitus tipo 2"))
    if cronico:
        ultimo = rng.randint(60, 260)
        b.add(aps, "consulta", "Control PSCV", d(ultimo), "Registro de atención", 6,
              resumen="Control cardiovascular programado.")
        b.add(aps, "control", "Control PSCV", d(ultimo), "Agenda de controles", 6, programado=d(ultimo - 180),
              estado="pendiente", prestacion="control_cronico")
    if edad < 10:
        b.add(aps, "control", "Control de niño sano", d(90), "Programa infantil", 2,
              programado=hoy + timedelta(days=rng.randint(-20, 40)), estado="pendiente", prestacion="nino_sano")
    if sexo == "F" and 18 <= edad <= 40 and rng.random() < .15:
        b.add(aps, "condicion", "Embarazo en curso", d(70), "Ingreso prenatal", 1, desde=d(70))
        b.add(aps, "control", "Control prenatal", d(30), "Agenda de controles", 2,
              programado=hoy + timedelta(days=rng.randint(-5, 20)), estado="pendiente", prestacion="matrona")
    if edad >= 65 or cronico:
        b.add(aps, "control", "Vacuna influenza (campaña)", d(150), "Programa Nacional de Inmunizaciones", 7,
              programado=d(rng.randint(-10, 60)), estado="pendiente", prestacion="vacunacion")
    if rng.random() < .2:
        alergeno, reaccion = rng.choice([("Penicilina", "Exantema"), ("AINE", "Angioedema"),
                                         ("Sulfas", "Urticaria"), ("Látex", "Dermatitis de contacto")])
        b.add(rng.choice([aps, "hrt"]), "alergia", alergeno, d(rng.randint(100, 2000)), "Alergias", 1,
              reaccion=reaccion)
    if edad >= 18 and rng.random() < .45:
        esp = rng.choice(["Cardiología", "Traumatología", "Oftalmología", "Medicina interna"])
        b.add("hrt", "consulta", f"{esp} (interconsulta)", d(rng.randint(20, 300)), f"Policlínico de {esp}", 2,
              resumen="Evaluación por especialista. Ver detalle en el registro de la atención.")
        b.examen("hrt", "Hemoglobina", round(rng.uniform(10.5, 15.5), 1), d(rng.randint(20, 300)), 3)
    nac = date(hoy.year - edad, rng.randint(1, 12), rng.randint(1, 28))
    return Paciente(nombre, nac, sexo, aps), b.items


def _demo(run: str, est: str) -> Resultado:
    t0 = time.perf_counter()
    hoy = today_local()
    paciente, registros = _caso_demo(hoy) if run == CASO_DEMO else _caso_generico(run, hoy)
    propios = [r for r in registros if r.cita.establecimiento_id == est]
    time.sleep(_rng(run, est).uniform(.05, .35))  # latencia simulada de cada base
    ms = (time.perf_counter() - t0) * 1000
    if not propios:
        return Resultado(est, "sin_registros", ms)
    return Resultado(est, "ok", ms, paciente, propios)


# ======================= adaptador FHIR R4 (referencia) =======================

def _fhir_urls() -> dict[str, str]:
    out = {}
    for par in os.getenv("FHIR_URLS", "").split(","):
        k, _, v = par.partition("=")
        if k.strip() and v.strip():
            out[k.strip()] = v.strip().rstrip("/")
    return out


def _fecha(s: str | None) -> date | None:
    try:
        return date.fromisoformat((s or "")[:10])
    except ValueError:
        return None


def _texto(cc: dict | None) -> str:
    cc = cc or {}
    return cc.get("text") or next((c.get("display") for c in cc.get("coding", []) if c.get("display")), "Sin nombre")


def _fhir(run: str, est: str) -> Resultado:
    t0 = time.perf_counter()
    base = _fhir_urls().get(est)
    if not base:
        return Resultado(est, "error", 0, error="Establecimiento sin servidor FHIR configurado")
    system = os.getenv("FHIR_RUN_SYSTEM", "urn:oid:2.16.152.1.2.1.1")  # ajustar al identificador del RUN del sistema
    headers = {"Accept": "application/fhir+json"}
    if os.getenv("FHIR_TOKEN"):
        headers["Authorization"] = f"Bearer {os.getenv('FHIR_TOKEN')}"
    with httpx.Client(base_url=base, headers=headers, timeout=TIMEOUT_S) as c:
        def buscar(recurso: str, **params) -> list[dict]:
            r = c.get(f"/{recurso}", params=params)
            r.raise_for_status()
            return [e["resource"] for e in r.json().get("entry", []) if "resource" in e]

        pacientes = buscar("Patient", identifier=f"{system}|{run}")
        if not pacientes:
            return Resultado(est, "sin_registros", (time.perf_counter() - t0) * 1000)
        p = pacientes[0]
        exp = next((i.get("value") for i in p.get("identifier", [])
                    if any(cd.get("code") == "MR" for cd in (i.get("type") or {}).get("coding", []))), p["id"])
        nombre = " ".join((p.get("name") or [{}])[0].get("given", []) + [(p.get("name") or [{}])[0].get("family", "")])
        b = _Builder(run)

        def cita(recurso: dict, fecha: date | None, seccion: str) -> Cita:
            return Cita(est, exp, fecha or date.min, f"{seccion} ({recurso['resourceType']}/{recurso['id']})")

        for cnd in buscar("Condition", patient=p["id"]):
            activo = any(x.get("code") == "active" for x in (cnd.get("clinicalStatus") or {}).get("coding", []))
            f = _fecha(cnd.get("recordedDate") or cnd.get("onsetDateTime"))
            b.n += 1
            b.items.append(Registro(f"R{b.n}", "condicion" if activo else "antecedente", _texto(cnd.get("code")),
                                    cita(cnd, f, "Problemas de salud"), {"desde": f}))
        for mr in buscar("MedicationRequest", patient=p["id"], status="active"):
            dosis = ((mr.get("dosageInstruction") or [{}])[0]).get("text")
            b.n += 1
            b.items.append(Registro(f"R{b.n}", "medicamento", _texto(mr.get("medicationCodeableConcept")),
                                    cita(mr, _fecha(mr.get("authoredOn")), "Receta"), {"dosis": dosis}))
        for al in buscar("AllergyIntolerance", patient=p["id"]):
            reac = (((al.get("reaction") or [{}])[0].get("manifestation") or [{}])[0]).get("text")
            b.n += 1
            b.items.append(Registro(f"R{b.n}", "alergia", _texto(al.get("code")),
                                    cita(al, _fecha(al.get("recordedDate")), "Alergias"), {"reaccion": reac}))
        for ob in buscar("Observation", patient=p["id"], category="laboratory", _sort="-date", _count="100"):
            q = ob.get("valueQuantity") or {}
            rr = (ob.get("referenceRange") or [{}])[0]
            b.n += 1
            b.items.append(Registro(f"R{b.n}", "examen", _texto(ob.get("code")),
                                    cita(ob, _fecha(ob.get("effectiveDateTime")), "Laboratorio"),
                                    {"valor": q.get("value"), "unidad": q.get("unit"),
                                     "ref_min": (rr.get("low") or {}).get("value"),
                                     "ref_max": (rr.get("high") or {}).get("value"), "area": "Laboratorio"}))
        for dr in buscar("DiagnosticReport", patient=p["id"], category="imaging", _count="50"):
            b.n += 1
            b.items.append(Registro(f"R{b.n}", "examen", _texto(dr.get("code")),
                                    cita(dr, _fecha(dr.get("effectiveDateTime")), "Imagenología"),
                                    {"valor": None, "area": "Imagenología", "informe": dr.get("conclusion")}))
        for ap in buscar("Appointment", patient=p["id"], status="booked"):
            f = _fecha(ap.get("start"))
            b.n += 1
            b.items.append(Registro(f"R{b.n}", "control", _texto((ap.get("serviceType") or [{}])[0]),
                                    cita(ap, f, "Agenda"), {"programado": f, "estado": "pendiente"}))
    paciente = Paciente(nombre.strip() or "Sin nombre", _fecha(p.get("birthDate")),
                        {"female": "F", "male": "M"}.get(p.get("gender")), None)
    return Resultado(est, "ok" if b.items else "sin_registros", (time.perf_counter() - t0) * 1000, paciente, b.items)


# ======================= consulta en paralelo =======================

def consultar_uno(run: str, est: str) -> Resultado:
    modo = os.getenv("FUENTES_MODE", "demo")
    try:
        res = _fhir(run, est) if modo == "fhir" else _demo(run, est)
    except Exception as exc:  # noqa: BLE001
        log.warning("Fuente %s falló: %s", est, exc)
        return Resultado(est, "error", 0, error=type(exc).__name__)
    for r in res.registros:  # identificador único en toda la red
        r.id = f"{est}:{r.id}"
    return res


def consultar(run: str, establecimientos: list[str], timeout: float | None = None) -> Iterator[Resultado]:
    """Consulta todas las bases a la vez y entrega cada resultado apenas llega (para informar
    el progreso). Las que no responden a tiempo se informan como `tiempo_agotado`."""
    limite = timeout or TIMEOUT_S
    if not establecimientos:
        return
    pool = ThreadPoolExecutor(max_workers=len(establecimientos))
    futuros = {pool.submit(consultar_uno, run, e): e for e in establecimientos}
    pendientes = set(establecimientos)
    try:
        for f in as_completed(futuros, timeout=limite):
            pendientes.discard(futuros[f])
            yield f.result()
    except TimeoutError:
        for e in sorted(pendientes):
            yield Resultado(e, "tiempo_agotado", limite * 1000, error=f"Sin respuesta en {limite:g} s")
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
