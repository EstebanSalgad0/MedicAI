"""Piezas comunes para levantar un microservicio FastAPI."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import FastAPI, Header, HTTPException
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker

INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "")


def setup_logging(name: str) -> logging.Logger:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s [" + name + "] %(name)s: %(message)s",
    )
    return logging.getLogger(name)


def create_service(name: str, description: str, on_startup: Callable[[], None] | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if on_startup:
            on_startup()
        yield

    app = FastAPI(title=f"MedicAI · {name}", description=description, version="1.0.0", lifespan=lifespan)

    @app.get("/health", tags=["infra"])
    def health():
        return {"status": "ok", "service": name}

    return app


def require_internal(x_internal_token: str = Header(default="")) -> None:
    """Protege endpoints internos (servicio a servicio). Si INTERNAL_TOKEN no está
    definido (desarrollo local) se permite el acceso."""
    if INTERNAL_TOKEN and x_internal_token != INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="Token interno inválido")


class Base(DeclarativeBase):
    pass


def make_db(default_sqlite: str):
    """Motor y fábrica de sesiones. Cada servicio tiene su propia base de datos
    (patrón database-per-service); en local cae a SQLite."""
    url = os.getenv("DATABASE_URL", f"sqlite:///{default_sqlite}")
    if url.startswith("postgresql"):
        ensure_database(url)
    kwargs = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def ensure_database(url: str) -> None:
    """Crea la base del servicio si no existe. init.sql solo corre al crear el volumen de
    PostgreSQL; así los servicios nuevos funcionan también en instalaciones existentes."""
    u = make_url(url)
    try:
        admin = create_engine(u.set(database="postgres"), isolation_level="AUTOCOMMIT")
        with admin.connect() as c:
            if not c.execute(text("SELECT 1 FROM pg_database WHERE datname = :d"), {"d": u.database}).scalar():
                c.execute(text(f'CREATE DATABASE "{u.database}"'))
        admin.dispose()
    except Exception as exc:  # noqa: BLE001
        logging.getLogger("medicai.db").warning("No se pudo verificar la base %s: %s", u.database, exc)


def ensure_columns(engine, table: str, columns: dict[str, str]) -> None:
    """Migración mínima: agrega columnas nuevas a una tabla existente ({nombre: tipo SQL})."""
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return
    have = {c["name"] for c in insp.get_columns(table)}
    with engine.begin() as c:
        for name, ddl in columns.items():
            if name not in have:
                c.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
