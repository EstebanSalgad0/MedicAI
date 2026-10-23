"""RUN chileno: limpieza, validación del dígito verificador (módulo 11) y formato."""
from __future__ import annotations

import re


def clean(raw: str) -> str | None:
    """'12.345.678-5' -> '12345678-5'. None si no parece un RUN."""
    t = re.sub(r"[^0-9kK]", "", raw or "").upper()
    if not 7 <= len(t) <= 9:
        return None
    return f"{t[:-1]}-{t[-1]}"


def dv(number: int) -> str:
    total, factor = 0, 2
    for d in reversed(str(number)):
        total += int(d) * factor
        factor = 2 if factor == 7 else factor + 1
    r = 11 - total % 11
    return {11: "0", 10: "K"}.get(r, str(r))


def valid(raw: str) -> str | None:
    """Devuelve el RUN limpio si el dígito verificador es correcto."""
    run = clean(raw)
    if not run:
        return None
    num, digit = run.split("-")
    return run if num.isdigit() and dv(int(num)) == digit else None


def fmt(run: str) -> str:
    num, digit = run.split("-")
    return f"{int(num):,}".replace(",", ".") + f"-{digit}"


def mask(run: str) -> str:
    """Para mostrar en pantalla sin exponer el RUN completo: 12.***.**8-5"""
    f = fmt(run)
    return f[:2] + re.sub(r"\d", "*", f[2:-3]) + f[-3:]
