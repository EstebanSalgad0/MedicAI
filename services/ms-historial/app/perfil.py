"""Perfil sintético del paciente (Módulo 1): resumen, línea de tiempo, alertas y antecedentes.

Prioridad cuando el historial es extenso: (a) condiciones activas, (b) medicamentos vigentes,
(c) alertas, (d) últimos exámenes, (e) antecedentes. Todo dato lleva su cita; lo que no
está en las fuentes se informa como "no se encontró", nunca se completa.
"""
from __future__ import annotations

from datetime import date

from medicai_common import rut
from medicai_common.textutil import normalize

from . import clinica
from .fuentes import NOMBRE_EST, Paciente, Registro, Resultado

AVISO = ("Apoyo a la decisión clínica generado automáticamente. No reemplaza el juicio del profesional "
         "y requiere validación del médico tratante.")


def _item(r: Registro, texto: str | None = None) -> dict:
    return {"id": r.id, "texto": texto or r.nombre, "cita": r.cita.texto(), "establecimiento": r.cita.establecimiento,
            "fecha": r.cita.fecha.isoformat()}


def _agrupar(registros: list[Registro], texto) -> list[dict]:
    """Une el mismo dato registrado en varios establecimientos, conservando todas las citas."""
    grupos: dict[str, dict] = {}
    for r in sorted(registros, key=lambda x: x.cita.fecha, reverse=True):
        clave = normalize(texto(r))
        if clave in grupos:
            grupos[clave]["otras_citas"].append(r.cita.texto())
        else:
            grupos[clave] = {**_item(r, texto(r)), "otras_citas": []}
    return list(grupos.values())


def _no_encontrado(dato: str, fuentes: list[str]) -> str:
    return f"No se encontró {dato} en las fuentes disponibles ({', '.join(fuentes) or 'ninguna respondió'})."


def _edad(nac: date | None, hoy: date) -> int | None:
    if not nac:
        return None
    return hoy.year - nac.year - ((hoy.month, hoy.day) < (nac.month, nac.day))


def _paciente(run: str, resultados: list[Resultado], hoy: date) -> dict:
    con_datos = [r for r in resultados if r.paciente]
    if not con_datos:
        return {"run_mask": rut.mask(run), "nombre": None, "edad": None, "sexo": None, "inscripcion": None}
    p: Paciente = next((r.paciente for r in con_datos if r.paciente.inscripcion), con_datos[0].paciente)
    return {"run_mask": rut.mask(run), "nombre": p.nombre, "edad": _edad(p.nacimiento, hoy), "sexo": p.sexo,
            "inscripcion": NOMBRE_EST.get(p.inscripcion or "", None)}


def construir(run: str, resultados: list[Resultado], hoy: date) -> dict:
    registros = [reg for r in resultados for reg in r.registros]
    respondieron = [NOMBRE_EST.get(r.establecimiento_id, r.establecimiento_id)
                    for r in resultados if r.estado in ("ok", "sin_registros")]
    sin_respuesta = [NOMBRE_EST.get(r.establecimiento_id, r.establecimiento_id)
                     for r in resultados if r.estado in ("error", "tiempo_agotado")]
    por_tipo = lambda t: [r for r in registros if r.tipo == t]  # noqa: E731

    condiciones = _agrupar(por_tipo("condicion"), lambda r: r.nombre)
    meds = [m for m in por_tipo("medicamento") if clinica.vigente(m, hoy)]
    medicamentos = [{**_item(m, m.nombre), "dosis": m.detalle.get("dosis")} for m in
                    sorted(meds, key=lambda x: x.cita.fecha, reverse=True)]
    alergias = [{**a, "reaccion": next((r.detalle.get("reaccion") for r in por_tipo("alergia") if r.id == a["id"]),
                                       None)} for a in _agrupar(por_tipo("alergia"), lambda r: r.nombre)]
    alertas = [a.dict() for a in clinica.alertas(registros, hoy)]

    examenes = []
    for e in sorted(por_tipo("examen"), key=lambda x: x.cita.fecha, reverse=True):
        d = e.detalle
        lo, hi = d.get("ref_min"), d.get("ref_max")
        rango = (f"{lo}–{hi}" if lo is not None and hi is not None else f"≥ {lo}" if lo is not None
                 else f"≤ {hi}" if hi is not None else None)
        examenes.append({**_item(e), "nombre": e.nombre, "valor": d.get("valor"), "unidad": d.get("unidad"),
                         "rango": rango, "estado": clinica.fuera_de_rango(e), "area": d.get("area"),
                         "informe": d.get("informe")})

    faltantes = []
    if not condiciones:
        faltantes.append(_no_encontrado("registro de condiciones activas", respondieron))
    if not medicamentos:
        faltantes.append(_no_encontrado("registro de medicamentos vigentes", respondieron))
    if not alergias:
        faltantes.append(_no_encontrado("registro de alergias", respondieron)
                         + " La ausencia de registro no confirma que el paciente no tenga alergias.")
    if not examenes:
        faltantes.append(_no_encontrado("resultados de exámenes", respondieron))
    if sin_respuesta:
        faltantes.append(f"Sin respuesta de: {', '.join(sin_respuesta)}. El perfil puede estar incompleto.")

    controles = [{**_item(c), "programado": c.detalle.get("programado").isoformat() if c.detalle.get("programado")
                  else None, "estado": c.detalle.get("estado")} for c in por_tipo("control")]
    return {
        "paciente": _paciente(run, resultados, hoy),
        "fuentes": [r.resumen() for r in resultados],
        "resumen": {  # (a) condiciones, (b) medicamentos, (c) alertas relevantes
            "condiciones_activas": condiciones,
            "medicamentos_vigentes": medicamentos,
            "alergias": alergias,
            "alertas_altas": sum(a["nivel"] == "alta" for a in alertas),
            "faltantes": faltantes,
        },
        "alertas": alertas,
        "examenes": examenes,  # (d) cronológico, más reciente primero
        "controles": controles,
        "antecedentes": _agrupar(por_tipo("antecedente"), lambda r: r.nombre),  # (e)
        "atenciones": [{**_item(c), "resumen": c.detalle.get("resumen")}
                       for c in sorted(por_tipo("consulta"), key=lambda x: x.cita.fecha, reverse=True)],
        "registros": {r.id: r for r in registros},
        "aviso": AVISO,
        "sin_registros": not registros,
    }


def publico(perfil: dict) -> dict:
    """El perfil sin los objetos internos (para la respuesta HTTP)."""
    return {k: v for k, v in perfil.items() if k != "registros"}


# Controles que el chat puede sugerir al paciente al agendar (sin revelar diagnósticos)
PRESTACION_MOTIVO = {"control_cronico": "Tienes un control crónico pendiente",
                     "nino_sano": "Hay un control de niño sano pendiente",
                     "matrona": "Tienes un control prenatal pendiente",
                     "vacunacion": "Tienes una vacuna pendiente"}


def controles_sugeridos(resultados: list[Resultado], hoy: date) -> list[dict]:
    vistos, out = set(), []
    for reg in (x for r in resultados for x in r.registros):
        p = reg.detalle.get("prestacion")
        prog = reg.detalle.get("programado")
        if (reg.tipo == "control" and reg.detalle.get("estado") == "pendiente" and p in PRESTACION_MOTIVO
                and p not in vistos and prog and (prog - hoy).days <= 30):
            vistos.add(p)
            out.append({"prestacion": p, "motivo": PRESTACION_MOTIVO[p], "center_id": reg.cita.establecimiento_id})
    return out
