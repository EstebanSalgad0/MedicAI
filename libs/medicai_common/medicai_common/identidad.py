"""Cliente de `ms-identidad` para los servicios del chat.

El chat nunca pide RUN, claves ni datos de pago. Si un trámite necesita saber quién es el
paciente, se consulta su vínculo verificado con ClaveÚnica; si no existe, se le envía un
enlace de un solo uso para ingresar con ClaveÚnica fuera del chat.
"""
from __future__ import annotations

import logging
import os

import httpx

from .messages import Message, buttons

IDENTIDAD_URL = os.getenv("IDENTIDAD_URL", "http://ms-identidad:8000")
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "")
log = logging.getLogger("medicai.identidad")
_H = {"X-Internal-Token": INTERNAL_TOKEN}


def run_en_modo_cuidador(user_id: str) -> str | None:
    """En modo cuidador el id lleva el RUN del paciente a cargo: cui:<cuidador>:<RUN>.
    Ese RUN lo registró el cuidador tras ingresar con ClaveÚnica."""
    return user_id.rsplit(":", 1)[1] if user_id.startswith("cui:") else None


def vinculo(user_id: str) -> dict | None:
    try:
        r = httpx.get(f"{IDENTIDAD_URL}/internal/vinculos/{user_id}", headers=_H, timeout=3)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    except Exception as exc:  # noqa: BLE001
        log.warning("Identidad no disponible: %s", exc)
        return None


def run_verificado(user_id: str, max_horas: float | None = None) -> str | None:
    """RUN del paciente si su identidad está verificada (y es reciente, si se pide)."""
    acting = run_en_modo_cuidador(user_id)
    if acting:
        return acting
    v = vinculo(user_id)
    if not v or (max_horas is not None and v.get("horas_desde_verificacion", 1e9) > max_horas):
        return None
    return v["run"]


def enlace(user_id: str, proposito: str) -> tuple[str, int] | None:
    try:
        r = httpx.post(f"{IDENTIDAD_URL}/internal/solicitudes", json={"user_id": user_id, "proposito": proposito},
                       headers=_H, timeout=4)
        r.raise_for_status()
        d = r.json()
        return d["url"], d["minutos"]
    except Exception as exc:  # noqa: BLE001
        log.warning("No se pudo crear el enlace de ClaveÚnica: %s", exc)
        return None


def usuarios_de_run(run: str) -> list[str]:
    try:
        r = httpx.get(f"{IDENTIDAD_URL}/internal/vinculos", params={"run": run}, headers=_H, timeout=3)
        r.raise_for_status()
        return r.json().get("user_ids", [])
    except Exception as exc:  # noqa: BLE001
        log.warning("Identidad no disponible: %s", exc)
        return []


def pedir_claveunica(user_id: str, proposito: str, para: str, footer: str) -> Message:
    """Mensaje con el enlace seguro. `para`: «ver tus exámenes», «registrar a un familiar»..."""
    e = enlace(user_id, proposito)
    if not e:
        return buttons("😕 No pude iniciar la verificación de identidad en este momento. Inténtalo en unos "
                       "minutos o acércate a Admisión con tu cédula.", [("ate:humano", "💬 Hablar con persona")],
                       footer)
    url, minutos = e
    return Message(type="text", footer=footer, text=(
        f"🔐 Para {para} necesito confirmar que eres tú.\n\n"
        f"Entra con tu *ClaveÚnica* en este enlace seguro (vence en {minutos} minutos):\n{url}\n\n"
        "Cuando termines, te escribo por aquí para seguir.\n"
        "_Nunca te pediré tu RUN, tu clave ni datos de pago por este chat._"))
