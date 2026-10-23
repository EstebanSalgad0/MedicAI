"""Cálculo de indicadores a partir de los eventos.

Las metas corresponden a los atributos comprometidos en la formulación FONDEF y
en el Anexo 1 (tiempo de respuesta, resolución autónoma, satisfacción, adherencia,
tasa de fallbacks). Cada KPI se informa con su numerador y denominador para que
el equipo pueda auditar el cálculo.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import mean
from typing import Any, Iterable

from medicai_common.textutil import TZ

from .models import Event

TARGETS = {
    "latency_p95_ms": {"value": 5000, "op": "<=", "label": "Tiempo de respuesta p95 ≤ 5 s"},
    "autonomous_resolution_rate": {"value": 0.85, "op": ">=", "label": "Resolución autónoma ≥ 85 %"},
    "satisfaction_avg": {"value": 4.5, "op": ">=", "label": "Satisfacción ≥ 4,5 / 5"},
    "fallback_rate": {"value": 0.08, "op": "<=", "label": "Fallbacks < 8 %"},
    "adherence_rate": {"value": 0.70, "op": ">=", "label": "Adherencia ≥ 70 %"},
}


def pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * q
    f, c = int(k), min(int(k) + 1, len(s) - 1)
    return round(s[f] + (s[c] - s[f]) * (k - f), 1)


def ratio(num: int, den: int) -> dict[str, Any]:
    return {"value": round(num / den, 4) if den else None, "num": num, "den": den}


def status(key: str, value: float | None) -> str | None:
    t = TARGETS.get(key)
    if t is None or value is None:
        return None
    ok = value <= t["value"] if t["op"] == "<=" else value >= t["value"]
    return "ok" if ok else "below"


def summary(events: Iterable[Event]) -> dict[str, Any]:
    ev = list(events)
    by_type: dict[str, list[Event]] = defaultdict(list)
    for e in ev:
        by_type[e.type].append(e)
    inter = by_type["interaction"]
    text_inter = [e for e in inter if e.props.get("input") == "text"]
    lat = [e.props["latency_ms"] for e in inter if e.props.get("latency_ms") is not None]
    e2e = [e.props["end_to_end_ms"] for e in by_type["delivery"] if e.props.get("end_to_end_ms") is not None]
    started = len(by_type["flow_started"])
    resolved = sum(1 for e in by_type["flow_completed"] if e.props.get("resolved"))
    ratings = [e.props["rating"] for e in by_type["survey_response"] if e.props.get("rating")]
    taken, skipped, expired = (len(by_type[t]) for t in ("dose_taken", "dose_skipped", "dose_expired"))
    attended, no_show = len(by_type["appointment_attended"]), len(by_type["appointment_no_show"])
    pick_done, pick_missed = len(by_type["pickup_done"]), len(by_type["pickup_missed"])

    k = {
        "interactions": len(inter),
        "unique_users": len({e.user_hash for e in inter if e.user_hash}),
        "latency_avg_ms": round(mean(lat), 1) if lat else None,
        "latency_p50_ms": pct(lat, 0.5),
        "latency_p95_ms": pct(lat, 0.95),
        "end_to_end_p95_ms": pct(e2e, 0.95),
        "fallback_rate": ratio(sum(1 for e in text_inter if e.props.get("fallback")), len(text_inter)),
        "autonomous_resolution_rate": ratio(resolved, started),
        "flows_abandoned": len(by_type["flow_abandoned"]),
        "satisfaction_avg": {"value": round(mean(ratings), 2) if ratings else None, "n": len(ratings),
                             "distribution": dict(sorted(Counter(ratings).items()))},
        "survey_response_rate": ratio(len(ratings), sum(1 for e in inter if e.props.get("survey_sent"))
                                      or len(ratings)),
        "adherence_rate": ratio(taken, taken + skipped + expired),
        "no_show_rate": ratio(no_show, attended + no_show),
        "pickup_rate": ratio(pick_done, pick_done + pick_missed),
        "red_flags": sum(1 for e in inter if e.props.get("red_flag")) + len(by_type["red_flag_detected"]),
        "human_handoff_offered": sum(1 for e in inter if e.props.get("human_handoff_offered")),
        "errors": sum(1 for e in inter if e.props.get("error")),
        "appointments_booked": len(by_type["appointment_booked"]),
        "appointments_cancelled": len(by_type["appointment_cancelled"]),
        "attendance_confirmed": len(by_type["attendance_confirmed"]),
        "reminders_created": len(by_type["reminder_created"]),
        "doses": {"taken": taken, "skipped": skipped, "expired": expired},
        "triage": dict(Counter(e.props.get("nivel") for e in by_type["triage_completed"])),
        "referrals": dict(Counter(e.props.get("doc_type") for e in by_type["referral_guided"])),
        "nlu_sources": dict(Counter(e.props.get("nlu_source") for e in text_inter)),
    }
    k["targets"] = {
        key: {**t, "status": status(key, (k[key]["value"] if isinstance(k[key], dict) else k[key]))}
        for key, t in TARGETS.items()
    }
    return k


def timeseries(events: Iterable[Event]) -> list[dict[str, Any]]:
    days: dict[str, dict[str, Any]] = defaultdict(lambda: {"interactions": 0, "users": set(), "fallbacks": 0,
                                                           "lat": [], "resolved": 0, "started": 0})
    for e in events:
        d = days[local_day(e.ts)]
        if e.type == "interaction":
            d["interactions"] += 1
            if e.user_hash:
                d["users"].add(e.user_hash)
            d["fallbacks"] += 1 if e.props.get("fallback") else 0
            if e.props.get("latency_ms") is not None:
                d["lat"].append(e.props["latency_ms"])
        elif e.type == "flow_started":
            d["started"] += 1
        elif e.type == "flow_completed" and e.props.get("resolved"):
            d["resolved"] += 1
    return [{"date": k, "interactions": v["interactions"], "unique_users": len(v["users"]),
             "fallbacks": v["fallbacks"], "latency_p95_ms": pct(v["lat"], 0.95),
             "flows_started": v["started"], "flows_resolved": v["resolved"]} for k, v in sorted(days.items())]


def per_service(events: Iterable[Event]) -> list[dict[str, Any]]:
    s: dict[str, dict[str, Any]] = defaultdict(lambda: {"started": 0, "completed": 0, "resolved": 0, "abandoned": 0,
                                                        "turns": [], "duration": []})
    for e in events:
        if e.type not in ("flow_started", "flow_completed", "flow_abandoned"):
            continue
        row = s[e.service]
        if e.type == "flow_started":
            row["started"] += 1
        elif e.type == "flow_abandoned":
            row["abandoned"] += 1
        else:
            row["completed"] += 1
            row["resolved"] += 1 if e.props.get("resolved") else 0
            row["turns"].append(e.props.get("turns", 0))
            row["duration"].append(e.props.get("duration_s", 0))
    out = []
    for name, r in sorted(s.items()):
        out.append({"service": name, "started": r["started"], "completed": r["completed"], "resolved": r["resolved"],
                    "abandoned": r["abandoned"],
                    "resolution_rate": round(r["resolved"] / r["started"], 4) if r["started"] else None,
                    "avg_turns": round(mean(r["turns"]), 1) if r["turns"] else None,
                    "avg_duration_s": round(mean(r["duration"]), 1) if r["duration"] else None})
    return out


def intents(events: Iterable[Event]) -> list[dict[str, Any]]:
    c: dict[str, dict[str, Any]] = defaultdict(lambda: {"total": 0, "conf": [], "sources": Counter()})
    for e in events:
        if e.type == "interaction" and e.props.get("intent"):
            r = c[e.props["intent"]]
            r["total"] += 1
            if e.props.get("confidence") is not None:
                r["conf"].append(e.props["confidence"])
            r["sources"][e.props.get("nlu_source")] += 1
    return sorted(({"intent": k, "total": v["total"], "avg_confidence": round(mean(v["conf"]), 3) if v["conf"] else None,
                    "sources": dict(v["sources"])} for k, v in c.items()), key=lambda x: -x["total"])


def local_day(ts: datetime) -> str:
    return ts.replace(tzinfo=timezone.utc).astimezone(TZ).date().isoformat()


def _rating_block(rs: list[int]) -> dict[str, Any]:
    n = len(rs)
    return {"n": n, "avg": round(mean(rs), 2) if rs else None,
            "distribution": {str(r): rs.count(r) for r in range(1, 6)},
            "satisfied_rate": round(sum(1 for r in rs if r >= 4) / n, 4) if n else None,
            "dissatisfied_rate": round(sum(1 for r in rs if r <= 2) / n, 4) if n else None}


def satisfaction(events: Iterable[Event], limit: int = 50) -> dict[str, Any]:
    """Encuesta post-atención: promedio, reparto, evolución diaria, por trámite y últimas respuestas."""
    ev = list(events)
    resp = [e for e in ev if e.type == "survey_response" and e.props.get("rating")]
    sent = sum(1 for e in ev if e.type == "interaction" and e.props.get("survey_sent"))
    ratings = [int(e.props["rating"]) for e in resp]
    by_day: dict[str, list[int]] = defaultdict(list)
    by_service: dict[str, list[int]] = defaultdict(list)
    for e in resp:
        by_day[local_day(e.ts)].append(int(e.props["rating"]))
        by_service[e.props.get("flow_service") or "sin_dato"].append(int(e.props["rating"]))
    out = _rating_block(ratings)
    t = TARGETS["satisfaction_avg"]
    out.update({
        "sent": sent,
        "response_rate": round(len(ratings) / sent, 4) if sent else None,
        "target": {**t, "status": status("satisfaction_avg", out["avg"])},
        "by_day": [{"date": d, "avg": round(mean(v), 2), "n": len(v)} for d, v in sorted(by_day.items())],
        "by_service": sorted(({"service": s, **_rating_block(v)} for s, v in by_service.items()),
                             key=lambda x: -x["n"]),
        "recent": [{"ts": e.ts.replace(tzinfo=timezone.utc).isoformat(), "rating": int(e.props["rating"]),
                    "service": e.props.get("flow_service"), "channel": e.channel, "center": e.center,
                    "user": e.user_hash} for e in sorted(resp, key=lambda x: x.ts, reverse=True)[:limit]],
    })
    return out


def chatbot_panel(events: Iterable[Event], days: int = 14) -> dict[str, Any]:
    """Panel «chatbot» del tablero de gestión: auto-resolución, temas, satisfacción,
    desvío de baja complejidad a APS y oportunidad de los avisos de resultados."""
    ev = list(events)
    k = summary(ev)
    text_intents = Counter(e.props.get("intent") for e in ev if e.type == "interaction"
                           and e.props.get("input") == "text" and e.props.get("intent")
                           and e.props.get("intent") not in ("saludo", "despedida", "agradecer", "afirmar", "negar"))
    total = sum(text_intents.values())
    temas = [{"intent": i, "n": n, "pct": round(n / total, 4)} for i, n in text_intents.most_common(8)]
    desvio: dict[str, int] = defaultdict(int)
    for e in ev:
        if e.type == "triage_completed" and e.props.get("nivel") in ("control", "autocuidado"):
            desvio[local_day(e.ts)] += 1
    delays = [e.props.get("delay_s") for e in ev if e.type == "result_notified" and e.props.get("delay_s") is not None]
    return {
        "auto_resolution": k["autonomous_resolution_rate"],
        "satisfaction": k["satisfaction_avg"],
        "temas": temas,
        "desvio_aps": [{"date": d, "n": n} for d, n in sorted(desvio.items())],
        "desvio_aps_total": sum(desvio.values()),
        "results_notified": len(delays),
        "results_within_5_min": round(sum(1 for d in delays if d <= 300) / len(delays), 4) if delays else None,
        "handoffs": sum(1 for e in ev if e.type == "handoff_requested"),
        "gap_filled": sum(1 for e in ev if e.type == "gap_filled"),
        "caregiver_sessions": sum(1 for e in ev if e.type == "caregiver_acting"),
        "interactions": k["interactions"],
        "unique_users": k["unique_users"],
    }
