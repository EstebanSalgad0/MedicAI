"""Adaptador de disponibilidad de fármacos.

`local`: inventario propio de MedicAI, mantenido por funcionarios desde el dashboard.
`http`:  sistema de farmacia externo (p. ej. el registro clínico del CESFAM). Se espera
         `GET {STOCK_API_URL}/stock?centro=<id>&medicamento=<nombre>` -> {"status": "...", "stock": n}.
Definir el contrato real con las entidades asociadas es parte de las pruebas de
interoperabilidad (OE3 del proyecto).
"""
from __future__ import annotations

import logging
import os
from typing import Literal

import httpx
from sqlalchemy import select

from medicai_common.textutil import normalize

from .models import SessionLocal, StockItem

Status = Literal["available", "low", "none", "unknown"]
PROVIDER = os.getenv("STOCK_PROVIDER", "local")
API_URL = os.getenv("STOCK_API_URL", "")
log = logging.getLogger("stock")


def key(name: str) -> str:
    return " ".join(normalize(name).split())


def find_local(center_id: str, name: str) -> StockItem | None:
    k = key(name)
    with SessionLocal() as db:
        item = db.scalar(select(StockItem).where(StockItem.center_id == center_id, StockItem.key == k))
        if item:
            return item
        # coincidencia parcial: "losartan" encuentra "losartan 50 mg"
        return db.scalar(select(StockItem).where(StockItem.center_id == center_id,
                                                 StockItem.key.contains(k.split()[0] if k else k)))


def check(center_id: str, name: str) -> tuple[Status, str]:
    """Devuelve (estado, nombre_canónico)."""
    if PROVIDER == "http" and API_URL:
        try:
            r = httpx.get(f"{API_URL}/stock", params={"centro": center_id, "medicamento": name}, timeout=4)
            r.raise_for_status()
            return r.json().get("status", "unknown"), name
        except Exception as exc:  # noqa: BLE001
            log.warning("Proveedor de stock externo no respondió: %s", exc)
            return "unknown", name
    item = find_local(center_id, name)
    if not item:
        return "unknown", name
    if item.stock <= 0:
        return "none", item.name
    if item.stock < item.min_stock:
        return "low", item.name
    return "available", item.name
