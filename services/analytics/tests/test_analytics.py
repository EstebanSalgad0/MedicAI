import os
import sys
from pathlib import Path

DB = Path(__file__).parent / "test_an.db"
DB.unlink(missing_ok=True)
os.environ.update(DATABASE_URL=f"sqlite:///{DB}", DASHBOARD_USER="ana", DASHBOARD_PASSWORD="clave-segura")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)
client.__enter__()


def ev(type, service="orchestrator", user="569", **props):
    return {"type": type, "service": service, "user_id": user, "props": props}


def test_kpis_y_metas():
    events = [
        ev("interaction", input="text", latency_ms=120, intent="agendar_cita", nlu_source="rasa"),
        ev("interaction", input="text", latency_ms=300, fallback=True, intent="nlu_fallback", nlu_source="fallback"),
        ev("interaction", input="option", latency_ms=90, user="web:x"),
        ev("flow_started", service="agendamiento"), ev("flow_completed", service="agendamiento", resolved=True, turns=4),
        ev("flow_started", service="recordatorios"), ev("flow_abandoned", service="recordatorios"),
        ev("survey_response", rating=5), ev("survey_response", rating=4),
        ev("dose_taken", "recordatorios"), ev("dose_taken", "recordatorios"), ev("dose_skipped", "recordatorios"),
    ]
    assert client.post("/internal/events", json={"events": events}).json()["stored"] == len(events)
    k = client.get("/kpis").json()
    assert k["interactions"] == 3 and k["unique_users"] == 2
    assert k["fallback_rate"] == {"value": 0.5, "num": 1, "den": 2}
    assert k["autonomous_resolution_rate"]["value"] == 0.5
    assert k["satisfaction_avg"]["value"] == 4.5
    assert k["targets"]["satisfaction_avg"]["status"] == "ok"
    assert k["targets"]["fallback_rate"]["status"] == "below"
    assert round(k["adherence_rate"]["value"], 2) == 0.67
    assert client.get("/kpis", params={"channel": "web"}).json()["interactions"] == 1

    svc = {s["service"]: s for s in client.get("/services").json()}
    assert svc["agendamiento"]["resolution_rate"] == 1.0 and svc["recordatorios"]["abandoned"] == 1
    assert client.get("/timeseries").json()[0]["interactions"] == 3


def test_seudonimizacion_y_export():
    client.post("/internal/events", json={"events": [ev("interaction", user="56911112222", input="text")]})
    csv_text = client.get("/export.csv").text
    assert "56911112222" not in csv_text and "usuario_seudonimo" in csv_text


def test_login_y_verify():
    assert client.post("/auth/login", json={"username": "ana", "password": "mala"}).status_code == 401
    tok = client.post("/auth/login", json={"username": "ana", "password": "clave-segura"}).json()["token"]
    assert client.get("/auth/verify", headers={"Authorization": f"Bearer {tok}"}).json()["user"] == "ana"
    assert client.get("/auth/verify").status_code == 401


def test_panel_hospital_y_analitica_conversacional():
    h = client.get("/hospital").json()
    assert h["simulado"] and len(h["camas"]) == 8 and 0 < h["ocupacion_global"] < 1
    assert len(h["urgencias"]["llegadas"]) == 24 and isinstance(h["alertas"], list)
    for q, palabra in (("¿cuántas camas UCI quedan?", "UCI"), ("¿cómo va urgencias?", "espera"),
                       ("¿cómo van las listas de espera?", "lista de espera"), ("¿y los pabellones?", "pabellones"),
                       ("¿cómo va el chatbot?", "Auto-resolución"), ("¿cómo va el ausentismo?", "Ausentismo"),
                       ("dame un resumen", "Resumen")):
        r = client.post("/ask", json={"question": q}).json()
        assert palabra.lower() in r["answer"].lower(), (q, r)
    panel = client.get("/chatbot/panel").json()
    assert "temas" in panel and "desvio_aps" in panel
