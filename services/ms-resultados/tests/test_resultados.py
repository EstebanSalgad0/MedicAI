import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(__file__).parent / "test_res.db")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
Path(__file__).parent.joinpath("test_res.db").unlink(missing_ok=True)

from fastapi.testclient import TestClient  # noqa: E402

from app import dialog, main  # noqa: E402
from medicai_common import rut  # noqa: E402

client = TestClient(main.app)
client.__enter__()
TZ = dialog.now_local().tzinfo


def turn(state, option_id=None, text="", user="569444", name=None):
    r = client.post("/dialog", json={"user_id": user, "name": name, "text": text, "option_id": option_id,
                                     "state": state or {}})
    assert r.status_code == 200, r.text
    return r.json()


def test_rut():
    assert rut.valid("12.345.678-5") == "12345678-5"
    assert rut.valid("12345678-9") is None
    assert rut.mask("12345678-5") == "12.***.**8-5"


def test_verifica_identidad_y_no_muestra_valores():
    fake = datetime(2026, 10, 21, 8, 0, tzinfo=TZ)
    with patch.object(dialog, "now_local", lambda: fake):
        r = turn({})
        assert r["state"]["step"] == "run"
        r = turn(r["state"], text="12345678-9")
        assert "no es válido" in r["messages"][0]["text"]
        r = turn(r["state"], text="12.345.678-5")
        r = turn(r["state"], text="01-02-1960")
        body = r["messages"][0]["text"]
        assert "en proceso" in body and "disponible" in body and "no muestro valores" in body
        assert r["messages"][0]["options"][0]["id"] == "res:watch"
        # la segunda consulta del día no vuelve a pedir datos
        r = turn({})
        assert "Exámenes" in r["messages"][0]["text"]
        r = turn({}, option_id="res:watch")
        assert r["events"][0]["type"] == "result_watch"

    sent = []
    later = datetime(2026, 10, 21, 20, 0, tzinfo=TZ)
    with patch.object(main, "send", lambda u, m: sent.append(m) or True), patch.object(main, "now_local", lambda: later):
        assert main.tick()["notified"] >= 1
        assert main.tick()["notified"] == 0
    assert "ya está disponible" in sent[0][0].text


def test_fecha_incorrecta_se_rechaza():
    r = turn({}, user="569555")
    r = turn(r["state"], text="11.111.111-1", user="569555")
    r = turn(r["state"], text="05-05-1970", user="569555")
    # vence la verificación: se vuelve a pedir y una fecha distinta no pasa
    with patch.object(dialog, "VERIFY_HOURS", 0):
        r = turn({}, user="569555")
        assert r["state"]["step"] == "birth"
        r = turn(r["state"], text="06-06-1971", user="569555")
        assert "no coincide" in r["messages"][0]["text"]


def test_modo_cuidador_usa_rut_del_paciente():
    r = turn({}, user="cui:569666:12345678-5", name="Juan Pérez")
    assert r["state"] == {"step": "birth", "run": "12345678-5"} and "Juan Pérez" in r["messages"][0]["text"]
