"""Identidad de los funcionarios en las APIs del dashboard.

El token (JWT) lo emite `ms-identidad` tras el ingreso con ClaveÚnica, o `analytics` para
las cuentas locales de administración. Cada servicio lo verifica por su cuenta con el
mismo JWT_SECRET y decide según el rol:

  - Roles clínicos (médico, enfermería, matrona, ...): acceso a la ficha clínica (Módulo 1).
  - Admisión/SOME, gestión y administración: agendas y derivaciones (Módulo 3), nunca fichas.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, Header, HTTPException

ROL_NOMBRE = {
    "medico": "Médico/a", "enfermeria": "Enfermero/a", "matrona": "Matrona/ón", "nutricion": "Nutricionista",
    "kinesiologia": "Kinesiólogo/a", "psicologia": "Psicólogo/a", "odontologia": "Odontólogo/a",
    "some": "Admisión / SOME", "gestion": "Gestión", "admin": "Administración",
}
ROLES_CLINICOS = {"medico", "enfermeria", "matrona", "nutricion", "kinesiologia", "psicologia", "odontologia"}
ROLES_AGENDA = ROLES_CLINICOS | {"some", "gestion", "admin"}


def _secret() -> str:
    return os.getenv("JWT_SECRET", "cambiar-en-produccion")


@dataclass
class Funcionario:
    sub: str
    nombre: str
    rol: str
    run: str | None = None
    establecimientos: list[str] = field(default_factory=list)
    metodo: str = "local"  # claveunica | local

    @property
    def clinico(self) -> bool:
        return self.rol in ROLES_CLINICOS

    @property
    def firma(self) -> str:
        return f"{self.nombre} ({ROL_NOMBRE.get(self.rol, self.rol)})"

    def claims(self) -> dict:
        return {"sub": self.sub, "nombre": self.nombre, "rol": self.rol, "run": self.run,
                "establecimientos": self.establecimientos, "metodo": self.metodo}


def emitir(f: Funcionario, horas: int | None = None) -> tuple[str, datetime]:
    exp = datetime.now(timezone.utc) + timedelta(hours=horas or int(os.getenv("JWT_HOURS", "8")))
    return jwt.encode({**f.claims(), "exp": exp}, _secret(), algorithm="HS256"), exp


def leer(token: str) -> Funcionario:
    data = jwt.decode(token, _secret(), algorithms=["HS256"])
    return Funcionario(sub=data["sub"], nombre=data.get("nombre") or data["sub"], rol=data.get("rol", "admin"),
                       run=data.get("run"), establecimientos=list(data.get("establecimientos") or []),
                       metodo=data.get("metodo", "local"))


def funcionario(authorization: str = Header(default="")) -> Funcionario:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Falta token")
    try:
        return leer(authorization[7:])
    except jwt.PyJWTError:
        raise HTTPException(401, "Token inválido o expirado") from None


def requiere_clinico(f: Funcionario = Depends(funcionario)) -> Funcionario:
    """Ficha clínica: solo profesionales de salud que ingresaron con ClaveÚnica."""
    if not f.clinico:
        raise HTTPException(403, "Su rol no tiene acceso a información clínica de pacientes.")
    if f.metodo != "claveunica":
        raise HTTPException(403, "El acceso a la ficha clínica requiere ingresar con ClaveÚnica.")
    return f


def requiere_agenda(f: Funcionario = Depends(funcionario)) -> Funcionario:
    if f.rol not in ROLES_AGENDA:
        raise HTTPException(403, "Su rol no tiene acceso a la gestión de agendas y derivaciones.")
    return f
