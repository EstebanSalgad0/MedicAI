"""Operación hospitalaria del Hospital Regional de Talca para el panel de gestión.

⚠️ DATOS SIMULADOS. La especificación pide, en el prototipo, simular con datos de
muestra lo que en producción vendrá del HIS y del sistema de camas (HL7 FHIR R4:
Location, Encounter, Appointment). Los valores siguen patrones horarios realistas y
son estables dentro de cada hora, para que el panel no «salte» al recargar.
Para conectar los datos reales basta con reemplazar `snapshot()`.
"""
from __future__ import annotations

import hashlib
import math
import random
from datetime import datetime

SERVICIOS = [  # (servicio, camas, ocupación base)
    ("Medicina interna", 64, 0.88), ("Cirugía", 52, 0.82), ("Pediatría", 30, 0.70),
    ("Gineco-obstetricia", 34, 0.74), ("Traumatología", 30, 0.86), ("Psiquiatría", 18, 0.80),
    ("UCI adulto", 14, 0.90), ("UTI / TIM", 16, 0.84),
]
BOX_OBSERVACION = 24
PABELLONES = 10
META_ESPERA_URGENCIA_MIN = 30


def _rng(now: datetime, salt: str = "") -> random.Random:
    return random.Random(int(hashlib.sha256(f"{now:%Y-%m-%d-%H}{salt}".encode()).hexdigest(), 16))


def _llegadas(hour: int, rng: random.Random) -> int:
    """Llegadas a urgencia por hora: mínimo de madrugada, peaks a media mañana y al anochecer."""
    base = 6 + 9 * math.exp(-((hour - 11) ** 2) / 8) + 7 * math.exp(-((hour - 19) ** 2) / 6)
    return max(1, round(base + rng.uniform(-2, 2)))


def snapshot(now: datetime) -> dict:
    rng = _rng(now)
    camas = []
    for nombre, total, base in SERVICIOS:
        ocupadas = min(total, round(total * min(0.99, max(0.5, base + rng.uniform(-0.06, 0.08)))))
        camas.append({"servicio": nombre, "total": total, "ocupadas": ocupadas,
                      "pct": round(ocupadas / total, 4), "disponibles": total - ocupadas})
    total = sum(c["total"] for c in camas)
    ocup = sum(c["ocupadas"] for c in camas)
    uci = next(c for c in camas if c["servicio"] == "UCI adulto")

    llegadas = [{"hora": f"{h:02d}:00", "hoy": _llegadas(h, _rng(now.replace(hour=h), "u")) if h <= now.hour else None,
                 "promedio": _llegadas(h, random.Random(h))} for h in range(24)]
    en_espera = max(2, round(_llegadas(now.hour, rng) * rng.uniform(1.0, 2.2)))
    espera_media = round(18 + en_espera * rng.uniform(1.1, 1.9))
    box_ocup = min(BOX_OBSERVACION, round(BOX_OBSERVACION * rng.uniform(0.78, 1.0)))
    boarding = rng.randint(2, 11)

    pab_util = round(rng.uniform(0.66, 0.9), 4)
    pab = {"pabellones": PABELLONES, "utilizacion": pab_util, "cirugias_programadas": rng.randint(22, 34),
           "suspensiones": rng.randint(0, 5), "puntualidad_primera_hora": round(rng.uniform(0.55, 0.85), 4)}
    listas = {"pacientes": rng.randint(8200, 8900), "mediana_dias": rng.randint(160, 230),
              "cumplimiento_ges": round(rng.uniform(0.9, 0.98), 4),
              "por_especialidad": [{"especialidad": e, "pacientes": rng.randint(400, 2100), "mediana_dias": rng.randint(60, 380)}
                                   for e in ("Oftalmología", "Traumatología", "Cardiología", "Ginecología", "Otorrino",
                                             "Dermatología", "Neurología")]}
    return {
        "simulado": True,
        "generado": now.isoformat(timespec="minutes"),
        "camas": camas,
        "camas_total": total,
        "ocupacion_global": round(ocup / total, 4),
        "uci_disponibles": uci["disponibles"],
        "uci_pct": uci["pct"],
        "urgencias": {"en_espera": en_espera, "espera_media_min": espera_media, "meta_min": META_ESPERA_URGENCIA_MIN,
                      "box_observacion": BOX_OBSERVACION, "box_ocupados": box_ocup,
                      "box_pct": round(box_ocup / BOX_OBSERVACION, 4), "boarding": boarding,
                      "pico_hora": max(llegadas, key=lambda x: x["promedio"])["hora"], "llegadas": llegadas},
        "pabellones": pab,
        "listas_espera": listas,
    }


def alerts(snap: dict, agenda_days: list[dict] | None, gap_today: int) -> list[dict]:
    """Reglas automáticas de la especificación. level: critical | warning | info | good."""
    out = []
    if snap["uci_pct"] >= 0.9:
        out.append({"level": "critical", "title": f"UCI al {snap['uci_pct']:.0%}",
                    "detail": "Sugerencia: revisar altas posibles y evaluar apertura de camas TIM."})
    u = snap["urgencias"]
    if u["box_pct"] >= 0.95:
        out.append({"level": "critical", "title": f"Box de observación al {u['box_pct']:.0%}",
                    "detail": "Sugerencia: activar flujo de egresos y gestión de camas para pacientes en espera."})
    if u["espera_media_min"] > u["meta_min"]:
        out.append({"level": "warning", "title": f"Espera media en urgencia: {u['espera_media_min']} min",
                    "detail": f"Supera la meta de {u['meta_min']} min. Aviso enviado a jefatura de urgencia."})
    for c in snap["camas"]:
        if c["servicio"] not in ("UCI adulto",) and c["pct"] >= 0.95:
            out.append({"level": "warning", "title": f"{c['servicio']} al {c['pct']:.0%}",
                        "detail": "Ocupación sobre el umbral de 95 %."})
    if agenda_days:
        rates = [d["no_show_rate"] for d in agenda_days if d.get("no_show_rate") is not None]
        if len(rates) >= 6:
            prev, last = sum(rates[:len(rates) // 2]) / (len(rates) // 2), sum(rates[len(rates) // 2:]) / (len(rates) - len(rates) // 2)
            if last < prev:
                out.append({"level": "good", "title": f"Ausentismo bajando: {last:.0%} vs {prev:.0%}",
                            "detail": "Efecto positivo de los recordatorios de 48 y 24 h."})
    if gap_today:
        out.append({"level": "good", "title": f"Fill-the-gap: {gap_today} hora(s) recuperada(s) hoy",
                    "detail": "Cupos liberados que tomaron pacientes de la lista de espera."})
    return out
