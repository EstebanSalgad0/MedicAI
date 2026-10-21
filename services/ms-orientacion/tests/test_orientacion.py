import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def turn(state, option_id=None, text="", start=False):
    r = client.post("/dialog", json={"user_id": "569333", "text": text, "option_id": option_id,
                                     "state": state or {}, "start": start})
    assert r.status_code == 200, r.text
    return r.json()


def test_flujo_autocuidado():
    r = turn({}, start=True)
    r = turn(r["state"], option_id="ori:cat:respiratorio")
    r = turn(r["state"], text="tengo tos leve, estornudos y congestión nasal")
    assert "estornudos" in r["messages"][0]["text"]
    r = turn(r["state"], option_id="ori:confirm:yes")
    assert "Autocuidado" in r["messages"][0]["text"]
    assert r["events"][0]["props"]["nivel"] == "autocuidado"
    assert r["state"] is None and r["resolved"]


def test_bandera_roja_salud_mental():
    r = turn({"step": "symptoms", "categoria": "saludmental"}, text="ya no quiero vivir")
    assert "4141" in r["messages"][0]["text"]
    assert r["events"][0]["type"] == "red_flag_detected"


def test_sin_regla_sugiere_cesfam_y_agendar():
    r = turn({"step": "confirm", "categoria": "bucal", "texto": "me duele algo raro", "detectados": []},
             option_id="ori:confirm:yes")
    assert "CESFAM" in r["messages"][0]["text"]
    assert r["messages"][1]["options"][0]["id"] == "agd:start"


def test_reglas_expuestas():
    assert len(client.get("/rules").json()["categorias"]) == 12
