"""Adaptador del sistema de laboratorio (LIS).

En el prototipo (`LIS_MODE=demo`) genera exámenes de muestra a partir del RUN, de
forma reproducible durante el día: varios disponibles, uno que se valida hoy a una
hora fija y otro que se valida mañana, para poder probar el aviso automático. Para
conectar el LIS real basta con implementar `exams_for` contra su API (p. ej. FHIR
DiagnosticReport).

Nunca se exponen valores ni interpretaciones: solo el estado de cada examen.
"""
from __future__ import annotations

import hashlib
import os
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta

LIS_MODE = os.getenv("LIS_MODE", "demo")
EXAMENES = [
    ("Hemograma", "Laboratorio", 1), ("Perfil bioquímico", "Laboratorio", 2), ("Glicemia", "Laboratorio", 1),
    ("Perfil lipídico", "Laboratorio", 2), ("Orina completa", "Laboratorio", 1), ("TSH", "Laboratorio", 3),
    ("Radiografía de tórax", "Imagenología", 2), ("Ecografía abdominal", "Imagenología", 3),
]


@dataclass
class Exam:
    name: str
    area: str
    taken_on: date
    ready_at: datetime

    def status(self, now: datetime) -> str:
        return "disponible" if self.ready_at <= now else "en_proceso"


def _at(day: date, rng: random.Random) -> datetime:
    return datetime.combine(day, datetime.min.time()) + timedelta(hours=rng.randint(9, 17),
                                                                  minutes=rng.choice([0, 15, 30, 45]))


def exams_for(run: str, today: date) -> list[Exam]:
    rng = random.Random(int(hashlib.sha256(f"{run}:{today.isoformat()}".encode()).hexdigest(), 16))
    picks = rng.sample(EXAMENES, rng.randint(3, 4))
    out = [Exam(picks[0][0], picks[0][1], today - timedelta(days=1), _at(today, rng)),       # se valida hoy
           Exam(picks[1][0], picks[1][1], today, _at(today + timedelta(days=1), rng))]       # se valida mañana
    for name, area, days in picks[2:]:
        taken = today - timedelta(days=rng.randint(days + 1, 20))
        out.append(Exam(name, area, taken, _at(taken + timedelta(days=days), rng)))
    return out
