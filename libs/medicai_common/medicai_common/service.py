"""Piezas comunes para levantar un microservicio FastAPI."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import FastAPI, Header, HTTPException
from sqlalchemy import create_engine
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
    kwargs = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)
