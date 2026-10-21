#!/usr/bin/env python3
"""Evaluación del NLU híbrido con el conjunto de prueba reservado.

Mide exactitud, F1 macro, tasa de fallback, qué capa resolvió cada mensaje
(Rasa / LLM / reglas) y latencia. El resultado es evidencia independiente del
desempeño del componente de IA (observación de ANID sobre métricas de TRL).

Uso (dentro de la red de docker compose):
    docker compose exec nlu python /app/evaluar_nlu.py
o desde el host, exponiendo el servicio NLU:
    python scripts/evaluar_nlu.py --nlu http://localhost:8001 \\
        --test services/nlu-rasa/tests/test_nlu.yml --salida reporte_nlu.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path


def load_examples(path: Path) -> list[tuple[str, str]]:
    import yaml  # pip install pyyaml

    out = []
    for block in yaml.safe_load(path.read_text())["nlu"]:
        if "intent" not in block:
            continue
        for line in block["examples"].splitlines():
            line = line.strip()
            if line.startswith("- "):
                text = line[2:]
                # quita anotaciones de entidades [valor](entidad)
                text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
                out.append((text, block["intent"]))
    return out


def parse(nlu_url: str, text: str, use_llm: bool) -> dict:
    req = urllib.request.Request(f"{nlu_url}/parse", method="POST",
                                 data=json.dumps({"text": text, "use_llm": use_llm}).encode(),
                                 headers={"Content-Type": "application/json",
                                          "X-Internal-Token": os.getenv("INTERNAL_TOKEN", "")})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nlu", default="http://localhost:8001")
    ap.add_argument("--test", default="services/nlu-rasa/tests/test_nlu.yml")
    ap.add_argument("--sin-llm", action="store_true", help="evalúa solo Rasa + reglas")
    ap.add_argument("--salida", default="")
    a = ap.parse_args()

    examples = load_examples(Path(a.test))
    rows, lat, sources = [], [], Counter()
    for text, gold in examples:
        r = parse(a.nlu, text, not a.sin_llm)
        rows.append({"texto": text, "esperada": gold, "predicha": r["intent"], "fuente": r["source"],
                     "confianza": r["confidence"], "ok": r["intent"] == gold})
        lat.append(r["latency_ms"])
        sources[r["source"]] += 1

    labels = sorted({g for _, g in examples})
    per = {}
    for lab in labels:
        tp = sum(1 for x in rows if x["predicha"] == lab and x["esperada"] == lab)
        fp = sum(1 for x in rows if x["predicha"] == lab and x["esperada"] != lab)
        fn = sum(1 for x in rows if x["predicha"] != lab and x["esperada"] == lab)
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        per[lab] = {"precision": round(p, 3), "recall": round(r, 3),
                    "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0, "n": tp + fn}
    acc = sum(x["ok"] for x in rows) / len(rows)
    by_source = defaultdict(lambda: [0, 0])
    for x in rows:
        by_source[x["fuente"]][0] += x["ok"]
        by_source[x["fuente"]][1] += 1
    report = {
        "ejemplos": len(rows),
        "exactitud": round(acc, 4),
        "f1_macro": round(statistics.mean(v["f1"] for v in per.values()), 4),
        "tasa_fallback": round(sources["fallback"] / len(rows), 4),
        "latencia_ms": {"mediana": statistics.median(lat), "max": max(lat)},
        "fuentes": dict(sources),
        "exactitud_por_fuente": {k: round(v[0] / v[1], 3) for k, v in by_source.items()},
        "por_intencion": per,
        "errores": [x for x in rows if not x["ok"]],
    }
    print(json.dumps({k: v for k, v in report.items() if k not in ("por_intencion", "errores")}, indent=2,
                     ensure_ascii=False))
    print("\nErrores:")
    for e in report["errores"]:
        print(f"  «{e['texto']}» esperada={e['esperada']} predicha={e['predicha']} ({e['fuente']})")
    if a.salida:
        Path(a.salida).write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"\nReporte completo: {a.salida}")


if __name__ == "__main__":
    main()
