import os
import sys
from pathlib import Path
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(__file__).parent / "test_ate.db")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
Path(__file__).parent.joinpath("test_ate.db").unlink(missing_ok=True)

from fastapi.testclient import TestClient  # noqa: E402

from app import dialog, main  # noqa: E402

client = TestClient(main.app)
client.__enter__()


def turn(state, option_id=None, text="", user="569777", start=False, intent=None, entities=None):
    r = client.post("/dialog", json={"user_id": user, "name": "Rosa", "text": text, "option_id": option_id,
                                     "state": state or {}, "start": start, "intent": intent,
                                     "entities": entities or {}})
    assert r.status_code == 200, r.text
    return r.json()


def test_fonasa_menu_y_detalle():
    r = turn({}, start=True, intent="tramites_fonasa")
    assert len(r["messages"][0]["options"]) == 6
    r = turn({}, option_id="ate:fonasa:bono")
    assert "Copago Cero" in r["messages"][0]["text"] and r["state"] is None


def test_info_visitas_preparacion():
    for key, word in (("info", "Admisión"), ("visitas", "acompañantes"), ("prep", "ayuno")):
        r = turn({}, option_id=f"ate:{key}")
        assert word in r["messages"][0]["text"]


def test_hablar_con_persona_crea_solicitud_con_contexto():
    r = turn({}, option_id="ate:humano")
    r = turn(r["state"], option_id="ate:humano:reclamo")
    with patch.object(dialog, "in_office_hours", lambda: False):
        r = turn(r["state"], text="Me cambiaron la hora sin avisar",
                 entities={"transcript": ["Paciente: hola", "MedicAI: ¿En qué te ayudo?"]})
    assert "fuera del horario" in r["messages"][0]["text"] and "OIRS" in r["messages"][0]["text"]
    tickets = client.get("/tickets").json()["items"]
    assert tickets[0]["topic"] == "reclamo" and tickets[0]["transcript"][0] == "Paciente: hola"

    with patch.object(main, "send", lambda u, m: True):
        out = client.post(f"/tickets/{tickets[0]['id']}/reply", json={"text": "Hola Rosa, lo revisamos."}).json()
    assert out["status"] == "answered" and out["replies"][0]["text"] == "Hola Rosa, lo revisamos."


def test_modo_cuidador_registro_y_activacion():
    r = turn({}, option_id="ate:cui", user="hija")
    assert r["messages"][0]["options"][0]["id"] == "ate:cui:new"
    r = turn({}, option_id="ate:cui:new", user="hija")
    r = turn(r["state"], text="Camila Soto", user="hija")
    r = turn(r["state"], text="12.345.678-9", user="hija")
    assert "no es válido" in r["messages"][0]["text"]
    r = turn(r["state"], text="12.345.678-5", user="hija")
    r = turn(r["state"], text="Juan Soto", user="hija")
    r = turn(r["state"], text="12.345.678-5", user="hija")
    assert "distinto" in r["messages"][0]["text"]
    r = turn(r["state"], text="11.111.111-1", user="hija")
    r = turn(r["state"], option_id="ate:cui:rel:hijo", user="hija")
    assert "Admisión" in r["messages"][0]["text"]
    r = turn(r["state"], option_id="ate:cui:save:yes", user="hija")
    act = r["messages"][0]["options"][0]["id"]
    r = turn({}, option_id=act, user="hija")
    assert r["acting"] == {"id": "cui:hija:11111111-1", "name": "Juan Soto"}
    r = turn({}, option_id="ate:cui:exit", user="hija")
    assert r["acting"] == {}
