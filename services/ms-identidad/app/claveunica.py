"""Cliente OpenID Connect de ClaveÚnica.

CLAVEUNICA_MODE:
  produccion  usa accounts.claveunica.gob.cl con las credenciales que entrega la División de
              Gobierno Digital al establecimiento (CLAVEUNICA_CLIENT_ID / _SECRET).
  demo        un simulador local reemplaza la página de ClaveÚnica (pruebas y demostraciones).
              El simulador queda rotulado como tal y se desactiva en producción.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import jwt

from medicai_common import rut

AUTHORIZE_URL = "https://accounts.claveunica.gob.cl/openid/authorize/"
TOKEN_URL = "https://accounts.claveunica.gob.cl/openid/token/"
USERINFO_URL = "https://accounts.claveunica.gob.cl/openid/userinfo/"


def mode() -> str:
    return os.getenv("CLAVEUNICA_MODE", "demo").lower()


def public_base() -> str:
    return os.getenv("PUBLIC_BASE_URL", "http://localhost:8080").rstrip("/")


def redirect_uri() -> str:
    return os.getenv("CLAVEUNICA_REDIRECT_URI") or f"{public_base()}/id/callback"


def authorize_url(state: str) -> str:
    if mode() == "demo":
        return f"/id/demo?{urlencode({'state': state})}"
    return AUTHORIZE_URL + "?" + urlencode({
        "client_id": os.getenv("CLAVEUNICA_CLIENT_ID", ""), "response_type": "code",
        "scope": "openid run name", "redirect_uri": redirect_uri(), "state": state,
    })


def _secret() -> str:
    return os.getenv("JWT_SECRET", "cambiar-en-produccion")


def demo_code(run: str, nombre: str) -> str:
    """Código de autorización del simulador: firmado y válido por 2 minutos."""
    exp = datetime.now(timezone.utc) + timedelta(minutes=2)
    return jwt.encode({"run": run, "nombre": nombre, "exp": exp, "aud": "claveunica-demo"}, _secret(), "HS256")


class ClaveUnicaError(Exception):
    pass


def exchange(code: str, state: str) -> dict:
    """Canjea el código por la identidad: {"run": "12345678-5", "nombre": "..."}."""
    if mode() == "demo":
        try:
            data = jwt.decode(code, _secret(), algorithms=["HS256"], audience="claveunica-demo")
        except jwt.PyJWTError as exc:
            raise ClaveUnicaError("Código inválido o vencido") from exc
        return {"run": data["run"], "nombre": data["nombre"]}
    try:
        tok = httpx.post(TOKEN_URL, timeout=10, data={
            "client_id": os.getenv("CLAVEUNICA_CLIENT_ID", ""),
            "client_secret": os.getenv("CLAVEUNICA_CLIENT_SECRET", ""),
            "redirect_uri": redirect_uri(), "grant_type": "authorization_code", "code": code, "state": state,
        })
        tok.raise_for_status()
        info = httpx.post(USERINFO_URL, timeout=10,
                          headers={"Authorization": f"Bearer {tok.json()['access_token']}"})
        info.raise_for_status()
        data = info.json()
    except Exception as exc:  # noqa: BLE001
        raise ClaveUnicaError(f"ClaveÚnica no respondió: {exc}") from exc
    ru = data.get("RolUnico") or {}
    run = rut.valid(f"{ru.get('numero', '')}-{ru.get('DV', '')}")
    if not run:
        raise ClaveUnicaError("ClaveÚnica no entregó un RUN válido")
    name = data.get("name") or {}
    nombre = " ".join((name.get("nombres") or []) + (name.get("apellidos") or [])).strip()
    return {"run": run, "nombre": nombre.title() or None}
