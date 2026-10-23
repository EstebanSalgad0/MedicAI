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


def test_sin_identidad_envia_enlace_de_claveunica_y_no_pide_run():
    with patch.object(dialog.identidad, "vinculo", lambda u: None),          patch.object(dialog.identidad, "enlace", lambda u, p: ("https://medicai.test/id/vincular/x1", 10)):
        r = turn({})
    body = r["messages"][0]["text"]
    assert "ClaveÚnica" in body and "https://medicai.test/id/vincular/x1" in body
    assert r["state"] is None and "Escribe tu" not in body


def test_verificacion_antigua_se_vuelve_a_pedir():
    viejo = {"run": "12345678-5", "nombre": "Ana", "horas_desde_verificacion": 30}
    with patch.object(dialog.identidad, "vinculo", lambda u: viejo),          patch.object(dialog.identidad, "enlace", lambda u, p: ("https://medicai.test/id/vincular/x2", 10)):
        r = turn({})
    assert "ClaveÚnica" in r["messages"][0]["text"]


def test_con_identidad_muestra_estado_sin_valores_y_avisa():
    v = {"run": "12345678-5", "nombre": "Ana", "horas_desde_verificacion": 1}
    fake = datetime(2026, 10, 21, 8, 0, tzinfo=TZ)
    with patch.object(dialog.identidad, "vinculo", lambda u: v), patch.object(dialog, "now_local", lambda: fake):
        r = turn({})
        body = r["messages"][0]["text"]
        assert "en proceso" in body and "disponible" in body and "no muestro valores" in body
        assert r["messages"][0]["options"][0]["id"] == "res:watch"
        r = turn({}, option_id="res:watch")
        assert r["events"][0]["type"] == "result_watch"

    sent = []
    later = datetime(2026, 10, 21, 20, 0, tzinfo=TZ)
    with patch.object(main, "send", lambda u, m: sent.append(m) or True), patch.object(main, "now_local", lambda: later):
        assert main.tick()["notified"] >= 1
        assert main.tick()["notified"] == 0
    assert "ya está disponible" in sent[0][0].text


def test_modo_cuidador_usa_rut_del_paciente():
    fake = datetime(2026, 10, 21, 8, 0, tzinfo=TZ)
    with patch.object(dialog, "now_local", lambda: fake):
        r = turn({}, user="cui:569666:12345678-5", name="Juan Pérez")
    assert "Juan Pérez" in r["messages"][0]["text"] and "12.***.**8-5" in r["messages"][0]["text"]
