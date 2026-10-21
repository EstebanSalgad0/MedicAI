"""Sesiones de conversación en Redis (con TTL), con respaldo en memoria para desarrollo."""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

log = logging.getLogger("orchestrator.sessions")
TTL = int(os.getenv("SESSION_TTL_SECONDS", "1800"))


class MemoryStore:
    def __init__(self) -> None:
        self._d: dict[str, tuple[float, str]] = {}

    def get(self, k: str) -> str | None:
        v = self._d.get(k)
        if not v or v[0] < time.time():
            self._d.pop(k, None)
            return None
        return v[1]

    def set(self, k: str, v: str, ex: int) -> None:
        self._d[k] = (time.time() + ex, v)

    def delete(self, k: str) -> None:
        self._d.pop(k, None)

    def incr(self, k: str, ex: int) -> int:
        n = int(self.get(k) or 0) + 1
        self.set(k, str(n), ex)
        return n


def make_store():
    url = os.getenv("REDIS_URL")
    if url:
        import redis
        r = redis.Redis.from_url(url, decode_responses=True)

        class RedisStore:
            def get(self, k):
                return r.get(k)

            def set(self, k, v, ex):
                r.set(k, v, ex=ex)

            def delete(self, k):
                r.delete(k)

            def incr(self, k, ex):
                n = r.incr(k)
                r.expire(k, ex)
                return n

        return RedisStore()
    log.warning("REDIS_URL no definido: sesiones en memoria (solo desarrollo)")
    return MemoryStore()


store = make_store()


def load(user_id: str) -> dict[str, Any]:
    raw = store.get(f"session:{user_id}")
    return json.loads(raw) if raw else {}


def save(user_id: str, session: dict[str, Any]) -> None:
    store.set(f"session:{user_id}", json.dumps(session, ensure_ascii=False, default=str), TTL)


def clear(user_id: str) -> None:
    store.delete(f"session:{user_id}")
