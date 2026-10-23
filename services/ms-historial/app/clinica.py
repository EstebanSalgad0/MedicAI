"""Reglas clínicas de apoyo: interacciones, alertas y apoyo diagnóstico.

⚠️ Son reglas de apoyo a la decisión. El equipo clínico del establecimiento debe revisarlas
y aprobarlas antes del uso con pacientes; cada regla tiene un código para trazarla.
Ninguna regla diagnostica ni prescribe: todas formulan "hipótesis a considerar" o
"sugerido evaluar" y citan los registros en que se basan.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from medicai_common.textutil import normalize

from .fuentes import Registro

IECA_ARA2 = {"losartan", "valsartan", "candesartan", "enalapril", "captopril", "lisinopril"}
ANTI_ALDOSTERONA = {"espironolactona", "eplerenona"}
AINES = {"ibuprofeno", "naproxeno", "diclofenaco", "ketoprofeno", "ketorolaco", "celecoxib", "meloxicam"}
ANTICOAGULANTES = {"warfarina", "acenocumarol"}
AAS = {"acido acetilsalicilico", "aspirina"}

# (código, grupo A, grupo B, nivel, riesgo, sugerencia)
INTERACCIONES = [
    ("INT-01", IECA_ARA2, ANTI_ALDOSTERONA, "alta", "Riesgo de hiperkalemia (IECA/ARA-II + antagonista de aldosterona).",
     "Sugerido evaluar potasio plasmático y función renal."),
    ("INT-02", IECA_ARA2, AINES, "alta", "AINE con IECA/ARA-II: riesgo de deterioro de la función renal y menor "
     "efecto antihipertensivo.", "Sugerido evaluar la necesidad del AINE y controlar función renal."),
    ("INT-03", ANTICOAGULANTES, AINES | AAS, "alta", "Riesgo de sangrado (anticoagulante + AINE/antiagregante).",
     "Sugerido evaluar la combinación con el médico tratante."),
    ("INT-04", AAS, AINES, "media", "AAS con AINE: mayor riesgo de sangrado digestivo.",
     "Sugerido evaluar protección gástrica o alternativa analgésica."),
    ("INT-05", {"clopidogrel"}, {"omeprazol", "esomeprazol"}, "media",
     "Omeprazol/esomeprazol pueden reducir el efecto de clopidogrel.", "Sugerido evaluar alternativa de IBP."),
    ("INT-06", {"levotiroxina"}, {"carbonato de calcio", "sulfato ferroso"}, "media",
     "Disminuye la absorción de levotiroxina.", "Sugerido evaluar separar las tomas."),
    ("INT-07", {"sertralina", "fluoxetina", "escitalopram", "paroxetina"}, {"tramadol"}, "alta",
     "Riesgo de síndrome serotoninérgico.", "Sugerido evaluar la combinación."),
    ("INT-08", {"sildenafil", "tadalafil"}, {"isosorbide", "nitroglicerina"}, "alta",
     "Riesgo de hipotensión grave.", "Sugerido evaluar la combinación."),
]
# alérgeno registrado -> fármacos relacionados
ALERGIA_CRUZADA = {
    "penicilina": {"penicilina", "amoxicilina", "ampicilina", "cloxacilina", "flucloxacilina"},
    "aine": AINES | AAS,
    "sulfa": {"cotrimoxazol", "sulfametoxazol"},
}


def nombre_norm(r: Registro) -> str:
    return normalize(r.nombre)


def _en(nombre: str, grupo: set[str]) -> bool:
    return any(g in nombre for g in grupo)


def vigente(m: Registro, hoy: date) -> bool:
    hasta = m.detalle.get("vigente_hasta")
    return hasta is None or hasta >= hoy


def fuera_de_rango(r: Registro) -> str:
    v, lo, hi = r.detalle.get("valor"), r.detalle.get("ref_min"), r.detalle.get("ref_max")
    if not isinstance(v, (int, float)):
        return "sin_valor"
    if lo is None and hi is None:
        return "sin_rango"
    if lo is not None and v < lo:
        return "bajo"
    if hi is not None and v > hi:
        return "alto"
    return "normal"


def ultimo(registros: list[Registro], contiene: str) -> Registro | None:
    exs = [r for r in registros if r.tipo == "examen" and contiene in nombre_norm(r)
           and isinstance(r.detalle.get("valor"), (int, float))]
    return max(exs, key=lambda r: r.cita.fecha) if exs else None


@dataclass
class Alerta:
    codigo: str
    tipo: str  # interaccion | alergia | control | riesgo | conciliacion
    nivel: str  # alta | media
    texto: str
    sugerencia: str
    registros: list[Registro] = field(default_factory=list)

    def dict(self) -> dict:
        return {"codigo": self.codigo, "tipo": self.tipo, "nivel": self.nivel, "texto": self.texto,
                "sugerencia": self.sugerencia, "citas": [r.cita.texto() for r in self.registros],
                "registros": [r.id for r in self.registros]}


def alertas(registros: list[Registro], hoy: date) -> list[Alerta]:
    out: list[Alerta] = []
    meds = [m for m in registros if m.tipo == "medicamento" and vigente(m, hoy)]
    conds = [c for c in registros if c.tipo == "condicion"]

    # interacciones entre fármacos vigentes (también entre establecimientos distintos)
    for cod, a, b, nivel, riesgo, sug in INTERACCIONES:
        ma = [m for m in meds if _en(nombre_norm(m), a)]
        mb = [m for m in meds if _en(nombre_norm(m), b)]
        if ma and mb:
            nombres = " + ".join(sorted({m.nombre.split(" ")[0] for m in ma + mb}))
            out.append(Alerta(cod, "interaccion", nivel, f"Posible interacción: {nombres}. {riesgo}", sug, ma + mb))

    # alergia registrada y fármaco relacionado vigente
    for al in (r for r in registros if r.tipo == "alergia"):
        grupo = next((g for k, g in ALERGIA_CRUZADA.items() if k in nombre_norm(al)), None)
        rel = [m for m in meds if grupo and _en(nombre_norm(m), grupo)]
        if rel:
            out.append(Alerta("ALG-01", "alergia", "alta",
                              f"Alergia registrada a {al.nombre} y fármaco relacionado vigente: "
                              f"{', '.join(m.nombre for m in rel)}.",
                              "Sugerido verificar la indicación con el médico tratante.", [al] + rel))

    # mismo fármaco con dosis distintas en establecimientos distintos (conciliación)
    por_farmaco: dict[str, list[Registro]] = {}
    for m in meds:
        por_farmaco.setdefault(nombre_norm(m).split(" ")[0], []).append(m)
    for grupo in por_farmaco.values():
        if len({normalize(m.nombre + (m.detalle.get("dosis") or "")) for m in grupo}) > 1 \
                and len({m.cita.establecimiento_id for m in grupo}) > 1:
            out.append(Alerta("CON-01", "conciliacion", "media",
                              f"{grupo[0].nombre.split(' ')[0]} registrado con indicaciones distintas en "
                              "más de un establecimiento.", "Sugerido conciliar la indicación vigente.", grupo))

    # controles pendientes vencidos
    for c in (r for r in registros if r.tipo == "control" and r.detalle.get("estado") == "pendiente"):
        prog = c.detalle.get("programado")
        if prog and prog < hoy:
            out.append(Alerta("CTL-01", "control", "media",
                              f"{c.nombre} pendiente desde el {prog:%d-%m-%Y} ({(hoy - prog).days} días).",
                              "Sugerido agendar o contactar al paciente.", [c]))

    # signos de riesgo en pacientes crónicos (umbrales configurables por el equipo clínico)
    dm = [c for c in conds if "diabetes" in nombre_norm(c)]
    a1c = ultimo(registros, "hba1c")
    if dm and a1c and a1c.detalle["valor"] >= 9:
        out.append(Alerta("RSG-01", "riesgo", "alta",
                          f"Diabetes con HbA1c {a1c.detalle['valor']} % (≥ 9 %): signo de descompensación.",
                          "Sugerido evaluar adherencia y ajuste terapéutico.", dm[:1] + [a1c]))
    vfg = ultimo(registros, "vfg")
    metf = [m for m in meds if "metformina" in nombre_norm(m)]
    if vfg and metf:
        v = vfg.detalle["valor"]
        if v < 30:
            out.append(Alerta("RSG-02", "riesgo", "alta", f"Metformina vigente con VFG {v} (< 30).",
                              "Sugerido evaluar suspensión según ficha técnica.", metf + [vfg]))
        elif v < 45:
            out.append(Alerta("RSG-03", "riesgo", "media", f"Metformina vigente con VFG {v} (30–45).",
                              "Sugerido evaluar ajuste de dosis.", metf + [vfg]))
    k = ultimo(registros, "potasio")
    if k and fuera_de_rango(k) == "alto":
        out.append(Alerta("RSG-04", "riesgo", "alta" if k.detalle["valor"] >= 6 else "media",
                          f"Potasio {k.detalle['valor']} mEq/L sobre el rango de referencia.",
                          "Sugerido controlar potasio y revisar fármacos que lo elevan.", [k]))
    cronicos = [c for c in conds if _en(nombre_norm(c), {"hipertension", "diabetes"})]
    if cronicos:
        controles = [r for r in registros if r.tipo == "consulta" and "pscv" in nombre_norm(r)]
        ult = max(controles, key=lambda r: r.cita.fecha) if controles else None
        if ult and (hoy - ult.cita.fecha) > timedelta(days=180):
            out.append(Alerta("RSG-05", "riesgo", "media",
                              f"Paciente crónico sin control PSCV registrado en {(hoy - ult.cita.fecha).days} días.",
                              "Sugerido agendar control.", cronicos[:1] + [ult]))
    orden = {"alta": 0, "media": 1}
    return sorted(out, key=lambda a: orden.get(a.nivel, 2))


# ======================= apoyo diagnóstico =======================

@dataclass
class Regla:
    codigo: str
    sintomas: tuple[str, ...]  # al menos uno en el cuadro clínico
    hipotesis: str
    examenes: tuple[str, ...]
    condiciones: tuple[str, ...] = ()  # registros que la refuerzan (condición, examen o fármaco)
    requiere_registro: bool = False  # solo se propone si hay un registro que la respalde
    urgente: bool = False


REGLAS = [
    Regla("DX-01", ("poliuria", "polidipsia", "baja de peso", "sed"), "Descompensación de diabetes mellitus",
          ("Glicemia", "HbA1c", "Orina completa (glucosuria y cetonuria)"), ("diabetes", "hba1c", "glicemia")),
    Regla("DX-02", ("edema", "disnea", "ortopnea", "fatiga", "cansancio"), "Insuficiencia cardíaca descompensada",
          ("NT-proBNP", "Radiografía de tórax", "Electrocardiograma", "Electrolitos plasmáticos y función renal"),
          ("ecocardiograma", "hipertension", "espironolactona"), requiere_registro=True),
    Regla("DX-03", ("debilidad", "calambre", "palpitacion", "arritmia"), "Hiperkalemia",
          ("Electrolitos plasmáticos", "Electrocardiograma", "Creatinina"),
          ("potasio", "espironolactona", "losartan", "enalapril"), requiere_registro=True),
    Regla("DX-04", ("disuria", "polaquiuria", "orina con mal olor", "ardor al orinar"), "Infección del tracto urinario",
          ("Orina completa", "Urocultivo"), ("diabetes",)),
    Regla("DX-05", ("cefalea", "mareo", "vision borrosa", "zumbido"), "Descompensación de hipertensión arterial",
          ("Presión arterial seriada", "Electrocardiograma", "Creatinina y orina completa"), ("hipertension",),
          requiere_registro=True),
    Regla("DX-06", ("dolor toracico", "dolor en el pecho", "opresion"), "Síndrome coronario agudo (descartar)",
          ("Electrocardiograma inmediato", "Troponinas"), ("hipertension", "diabetes", "dislipidemia"), urgente=True),
    Regla("DX-07", ("frio", "aumento de peso", "constipacion", "piel seca"), "Hipotiroidismo no controlado",
          ("TSH", "T4 libre"), ("hipotiroidismo", "tsh", "levotiroxina"), requiere_registro=True),
    Regla("DX-08", ("tos", "fiebre", "expectoracion", "sibilancia"), "Infección respiratoria baja o exacerbación "
          "de enfermedad respiratoria crónica", ("Radiografía de tórax", "Hemograma", "PCR", "Oximetría de pulso"),
          ("asma", "epoc")),
    Regla("DX-09", ("palidez", "fatiga", "cansancio"), "Anemia", ("Hemograma", "Ferritina y perfil de hierro"),
          ("hemoglobina", "enfermedad renal")),
]


def apoyo(cuadro: str, registros: list[Registro]) -> list[dict]:
    """Hipótesis a considerar según el cuadro que ingresa el profesional y los registros del paciente."""
    t = normalize(cuadro)
    out = []
    for regla in REGLAS:
        sintomas = [s for s in regla.sintomas if s in t]
        if not sintomas:
            continue
        respaldo = [r for r in registros if any(c in nombre_norm(r) for c in regla.condiciones)
                    and r.tipo in ("condicion", "examen", "medicamento", "antecedente")]
        if regla.requiere_registro and not respaldo:
            continue
        respaldo = sorted(respaldo, key=lambda r: r.cita.fecha, reverse=True)[:4]
        fundamentos = [{"texto": f"Referido en el cuadro clínico: {', '.join(sintomas)}.",
                        "cita": "[Cuadro clínico ingresado por el profesional en esta consulta]"}]
        fundamentos += [{"texto": _describe(r), "cita": r.cita.texto(), "registro": r.id} for r in respaldo]
        out.append({"codigo": regla.codigo, "hipotesis": f"Hipótesis a considerar: {regla.hipotesis}",
                    "fundamentos": fundamentos, "examenes_sugeridos": list(regla.examenes),
                    "urgente": regla.urgente, "origen": "regla clínica configurada",
                    "nota": "Requiere confirmación del médico tratante."})
    return sorted(out, key=lambda h: (not h["urgente"], -len(h["fundamentos"])))


def _describe(r: Registro) -> str:
    if r.tipo == "examen":
        v = r.detalle.get("valor")
        if v is None:
            return f"{r.nombre}: {r.detalle.get('informe') or 'informe sin conclusión'}"
        return f"{r.nombre}: {v} {r.detalle.get('unidad') or ''}".strip()
    if r.tipo == "medicamento":
        return f"Fármaco registrado: {r.nombre}"
    return f"{'Condición activa' if r.tipo == 'condicion' else 'Antecedente'}: {r.nombre}"
