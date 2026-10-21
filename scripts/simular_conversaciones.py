#!/usr/bin/env python3
"""Pruebas funcionales en entorno simulado (protocolo OE3).

Ejecuta guiones de conversación contra el sistema completo a través del gateway
(canal «web»/simulador), verifica que cada guion termine donde corresponde y
reporta latencias. Los eventos generados quedan marcados con canal «web», así
que nunca se mezclan con los indicadores de pacientes reales (WhatsApp).

Uso:
    python scripts/simular_conversaciones.py --url http://localhost:8080 \\
        --user admin --password <clave> --repeticiones 3
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import uuid
import urllib.request

# Cada paso: ("texto", ...) o ("opcion", id | índice) ; "espera" = texto que debe aparecer en la respuesta.
GUIONES = {
    "agendar_hora": [
        ("texto", "hola", "MedicAI"),
        ("texto", "quiero pedir hora con la matrona", None),  # el NLU detecta «matrona»: salta al CESFAM
        ("opcion", 0, None),           # primer CESFAM
        ("opcion", 0, None),           # primera hora disponible
        ("opcion", "agd:confirm:yes", "agendada"),
        ("opcion", "agd:confirm:yes", "no está vigente"),  # botón antiguo tocado de nuevo
    ],
    "recordatorio": [
        ("texto", "recuérdame tomar el losartán", None),
        ("texto", "Losartán 50 mg", None),
        ("opcion", "rec:freq:2", None),
        ("texto", "08:00", None),
        ("opcion", "rec:save:yes", "activos"),
    ],
    "orientacion": [
        ("texto", "me siento mal, tengo tos", None),
        ("opcion", "ori:cat:respiratorio", None),
        ("texto", "tos leve, estornudos y congestion nasal", None),
        ("opcion", "ori:confirm:yes", "Nivel de atención"),
    ],
    "guia_ruta": [
        ("texto", "me dieron una interconsulta", None),
        ("opcion", "der:type:interconsulta", None),
        ("opcion", "der:ges:no", "SOME"),
        ("opcion", "der:done", None),
    ],
    "farmacia": [
        ("texto", "farmacia", None),
        ("opcion", "med:rx:yes", None),
        ("texto", "metformina", None),
        ("opcion", "med:center:las_americas", "Metformina"),
        ("opcion", "med:freq:30", None),
        ("opcion", 1, None),
        ("opcion", "med:hour:08:00", "Listo"),
        ("opcion", "med:link:no", None),
    ],
    "alarma": [
        ("texto", "no puedo respirar", "131"),
    ],
    "no_entendido": [
        ("texto", "asdfgh qwerty", "No logré entenderte"),
    ],
}


def post(url, path, body, token=None):
    req = urllib.request.Request(f"{url}{path}", data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def run(url, token, name, steps):
    sid = f"sim-{name[:8]}-{uuid.uuid4().hex[:6]}"
    last, rtts, ok, fail_reason = None, [], True, None
    for kind, value, expect in steps:
        body = {"session_id": sid, "text": "", "option_id": None}
        if kind == "texto":
            body["text"] = value
        else:
            opts = [o for m in (last or {}).get("messages", []) for o in m.get("options", [])]
            if isinstance(value, int):
                if value >= len(opts):
                    ok, fail_reason = False, f"no hay opción #{value}"
                    break
                body["option_id"] = opts[value]["id"]
            else:
                body["option_id"] = value
        t0 = time.perf_counter()
        last = post(url, "/api/chat", body, token)
        rtts.append((time.perf_counter() - t0) * 1000)
        if expect:
            joined = " ".join(m["text"] for m in last["messages"])
            if expect.lower() not in joined.lower():
                ok, fail_reason = False, f"esperaba «{expect}» tras {kind} {value!r}"
                break
    return ok, fail_reason, rtts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8080")
    ap.add_argument("--user", default="admin")
    ap.add_argument("--password", required=True)
    ap.add_argument("--repeticiones", type=int, default=1)
    a = ap.parse_args()
    token = post(a.url, "/api/auth/login", {"username": a.user, "password": a.password})["token"]

    all_rtt, failures, total = [], [], 0
    for name, steps in GUIONES.items():
        for i in range(a.repeticiones):
            total += 1
            ok, reason, rtts = run(a.url, token, name, steps)
            all_rtt += rtts
            print(f"{'✔' if ok else '✘'} {name} #{i + 1}  ({len(rtts)} turnos, máx {max(rtts):.0f} ms)"
                  + ("" if ok else f"  → {reason}"))
            if not ok:
                failures.append((name, reason))
    q = statistics.quantiles(all_rtt, n=20) if len(all_rtt) > 1 else all_rtt * 19
    print(f"\nGuiones exitosos: {total - len(failures)}/{total}")
    print(f"Turnos: {len(all_rtt)} · ida y vuelta mediana {statistics.median(all_rtt):.0f} ms · p95 {q[18]:.0f} ms")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
