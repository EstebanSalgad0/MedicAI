"""Acceso a modelos de lenguaje con política on-premise.

El prompt exige que el modelo corra 100 % en local: ningún dato clínico sale del
establecimiento ni de la red asistencial. Por eso:

  - `ollama` / `local` / `openai`: API compatible con OpenAI alojada por el Servicio de
    Salud (p. ej. el contenedor `ollama` del perfil `llm` de docker-compose).
  - `anthropic`: proveedor externo. Queda bloqueado salvo que LLM_ALLOW_EXTERNAL=true,
    y aun así NUNCA se usa para datos clínicos (`clinical=True`).
  - `none`: sin modelo; todos los servicios funcionan con reglas.
"""
from __future__ import annotations

import logging
import os

import httpx

log = logging.getLogger("medicai.llm")

LOCAL_PROVIDERS = {"ollama", "local", "openai"}
EXTERNAL_PROVIDERS = {"anthropic"}


def _cfg() -> dict:
    return {
        "provider": os.getenv("LLM_PROVIDER", "none").lower(),
        "api_key": os.getenv("LLM_API_KEY", ""),
        "model": os.getenv("LLM_MODEL", "qwen2.5:7b"),
        "base_url": os.getenv("LLM_BASE_URL", "http://ollama:11434/v1").rstrip("/"),
        "timeout": float(os.getenv("LLM_TIMEOUT_SECONDS", "4")),
        "allow_external": os.getenv("LLM_ALLOW_EXTERNAL", "false").lower() == "true",
    }


def is_local() -> bool:
    return _cfg()["provider"] in LOCAL_PROVIDERS


def enabled(clinical: bool = False) -> bool:
    c = _cfg()
    if c["provider"] in LOCAL_PROVIDERS:
        return True
    if c["provider"] in EXTERNAL_PROVIDERS:
        if clinical:
            return False  # datos clínicos: solo modelo local, sin excepciones
        return c["allow_external"] and bool(c["api_key"])
    return False


def complete(system: str, user: str, *, max_tokens: int = 300, clinical: bool = False,
             timeout: float | None = None) -> str | None:
    """Texto generado por el modelo, o None si no hay modelo permitido o falló."""
    if not enabled(clinical):
        return None
    c = _cfg()
    wait = timeout or c["timeout"]
    try:
        if c["provider"] in EXTERNAL_PROVIDERS:
            r = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": c["api_key"], "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": c["model"], "max_tokens": max_tokens, "system": system,
                      "messages": [{"role": "user", "content": user}]},
                timeout=wait,
            )
            r.raise_for_status()
            return r.json()["content"][0]["text"]
        headers = {"Authorization": f"Bearer {c['api_key']}"} if c["api_key"] else {}
        r = httpx.post(
            f"{c['base_url']}/chat/completions", headers=headers, timeout=wait,
            json={"model": c["model"], "temperature": 0, "max_tokens": max_tokens,
                  "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as exc:  # noqa: BLE001
        log.warning("LLM no disponible o respuesta inválida: %s", exc)
        return None
