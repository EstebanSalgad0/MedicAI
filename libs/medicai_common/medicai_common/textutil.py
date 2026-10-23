from __future__ import annotations

import os
import re
import unicodedata
from datetime import date, datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo(os.getenv("APP_TZ", "America/Santiago"))


def normalize(t: str) -> str:
    """Minúsculas y sin tildes, para comparar texto libre."""
    t = (t or "").strip().lower()
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def now_local() -> datetime:
    return datetime.now(TZ)


def today_local() -> date:
    return now_local().date()


_HHMM = re.compile(r"\b(\d{1,2})(?::|\.|h)(\d{2})\b")
_HOUR_ONLY = re.compile(r"\b(\d{1,2})\s*(am|pm|hrs?|horas?)?\b")


def parse_times(txt: str) -> list[str]:
    """Extrae horas en formato HH:MM. Acepta '08:00 y 20:00', '8.30', '9 am', '21 hrs'."""
    t = normalize(txt)
    found: list[str] = []
    for h, m in _HHMM.findall(t):
        if int(h) < 24 and int(m) < 60:
            found.append(f"{int(h):02d}:{m}")
    if not found:
        for h, suf in _HOUR_ONLY.findall(t):
            hh = int(h)
            if suf == "pm" and hh < 12:
                hh += 12
            if hh < 24:
                found.append(f"{hh:02d}:00")
    # sin duplicados, en orden
    return sorted(dict.fromkeys(found))


def parse_date(txt: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(txt.strip(), fmt).date()
        except ValueError:
            pass
    return None


def slug(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", normalize(t)).strip("_")
