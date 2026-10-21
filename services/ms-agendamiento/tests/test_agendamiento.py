import os
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(__file__).parent / "test_agd.db")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
Path(__file__).parent.joinpath("test_agd.db").unlink(missing_ok=True)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)
client.__enter__()  # dispara startup


def turn(state, option_id=None, text="", start=False, intent=None):
    r = client.post("/dialog", json={"user_id": "569111", "name": "Ana", "text": text,
                                     "option_id": option_id, "state": state or {},
                                     "start": start, "intent": intent})
    assert r.status_code == 200, r.text
    return r.json()


def test_reserva_completa_y_cancelacion():
    r = turn({}, start=True, intent="agendar_cita")
    assert r["messages"][0]["type"] == "list"
    r = turn(r["state"], text="odontologia")  # texto libre que calza con la opción
    assert r["state"]["prestacion"] == "odontologia"
    r = turn(r["state"], option_id="agd:center:las_americas")
    slot_opt = r["messages"][0]["options"][1]["id"]
    r = turn(r["state"], option_id=slot_opt)
    assert r["state"]["step"] == "confirm"
    r = turn(r["state"], option_id="agd:confirm:yes")
    assert r["resolved"] is True and r["state"] is None
    assert r["events"][0]["type"] == "appointment_booked"

    # el cupo ya no se ofrece
    r = turn({}, start=True)
    r = turn(r["state"], option_id="agd:esp:odontologia")
    r = turn(r["state"], option_id="agd:center:las_americas")
    assert slot_opt not in [o["id"] for o in r["messages"][0]["options"]]

    appts = client.get("/appointments").json()
    assert len(appts) == 1
    r = turn({}, option_id=f"agd:cancel:{appts[0]['id']}")
    assert r["events"][0]["type"] == "appointment_cancelled"
    assert client.get("/appointments").json()[0]["status"] == "cancelled"


def test_mis_citas_vacio():
    r = turn({}, start=True, intent="ver_citas")
    assert "No tienes horas" in r["messages"][0]["text"]
