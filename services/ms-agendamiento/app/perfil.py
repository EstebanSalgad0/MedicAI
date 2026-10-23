"""Controles sugeridos según el perfil del paciente (Módulo 2: crónicos, niño sano, embarazo,
vacunas). Solo si el paciente ya verificó su identidad con ClaveÚnica; al chat solo llega la
prestación pendiente, nunca un diagnóstico."""
from __future__ import annotations

import logging
import os

import httpx

from medicai_common import identidad

HISTORIAL_URL = os.getenv("HISTORIAL_URL", "http://ms-historial:8000")
ACTIVO = os.getenv("PERFIL_SUGERENCIAS", "true").lower() == "true"
log = logging.getLogger("agendamiento.perfil")


def sugeridos(user_id: str) -> list[dict]:
    if not ACTIVO:
        return []
    run = identidad.run_verificado(user_id)
    if not run:
        return []
    try:
        r = httpx.get(f"{HISTORIAL_URL}/internal/controles-sugeridos/{run}",
                      headers={"X-Internal-Token": identidad.INTERNAL_TOKEN}, timeout=3)
        r.raise_for_status()
        return r.json().get("controles", [])
    except Exception as exc:  # noqa: BLE001
        log.warning("Historial no disponible para sugerir controles: %s", exc)
        return []
