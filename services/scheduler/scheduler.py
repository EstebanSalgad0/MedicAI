"""Programador central: cada TICK_SECONDS invoca /internal/jobs/tick en los servicios
que tienen tareas periódicas (recordatorios de toma, de hora y de retiro, seguimiento
de derivaciones). Reemplaza el hilo en memoria del prototipo, que se perdía al reiniciar
y se duplicaba con varios workers de gunicorn."""
import logging
import os
import time

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [scheduler] %(message)s")
log = logging.getLogger("scheduler")

TARGETS = [u.strip() for u in os.getenv(
    "TICK_TARGETS",
    "http://ms-recordatorios:8000,http://ms-agendamiento:8000,http://ms-medicamentos:8000,http://ms-derivacion:8000,"
    "http://ms-resultados:8000",
).split(",") if u.strip()]
INTERVAL = int(os.getenv("TICK_SECONDS", "60"))
HEADERS = {"X-Internal-Token": os.getenv("INTERNAL_TOKEN", "")}


def main() -> None:
    log.info("Scheduler iniciado: %s cada %ss", TARGETS, INTERVAL)
    while True:
        started = time.time()
        for url in TARGETS:
            try:
                r = httpx.post(f"{url}/internal/jobs/tick", headers=HEADERS, timeout=50)
                r.raise_for_status()
                result = r.json()
                if any(v for v in result.values()):
                    log.info("%s → %s", url, result)
            except Exception as exc:  # noqa: BLE001
                log.warning("Tick fallido en %s: %s", url, exc)
        time.sleep(max(1, INTERVAL - (time.time() - started)))


if __name__ == "__main__":
    main()
