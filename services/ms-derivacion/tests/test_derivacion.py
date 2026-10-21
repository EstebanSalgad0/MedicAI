import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

DB = Path(__file__).parent / "test_der.db"
DB.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{DB}"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app import main  # noqa: E402

client = TestClient(main.app)
client.__enter__()


def turn(state, option_id=None, text="", start=False):
    r = client.post("/dialog", json={"user_id": "569444", "text": text, "option_id": option_id,
                                     "state": state or {}, "start": start})
    assert r.status_code == 200, r.text
    return r.json()


def test_interconsulta_ges_con_seguimiento():
    r = turn({}, start=True)
    r = turn(r["state"], text="interconsulta")
    r = turn(r["state"], option_id="der:ges:si")
    assert "GES" in r["messages"][0]["text"]
    r = turn(r["state"], option_id="der:follow:7")
    assert r["resolved"] and {e["type"] for e in r["events"]} >= {"referral_guided"}

    sent = []
    later = main.now_local() + timedelta(days=8)
    with patch.object(main, "send", lambda u, m: sent.append(m) or True), \
         patch.object(main, "now_local", lambda: later):
        assert main.tick()["sent"] == 1
    r = turn({}, option_id=sent[0][0].options[0].id)
    assert r["events"][0]["props"]["contacted"] is True


def test_receta_ofrece_puentes_a_otros_servicios():
    r = turn({}, option_id="der:type:receta")
    ids = [o["id"] for o in r["messages"][0]["options"]]
    assert "rec:new" in ids and "med:start" in ids


def test_urgente_comuna_sin_datos():
    r = turn({}, option_id="der:type:urgente")
    r = turn(r["state"], option_id="der:sapu")
    r = turn(r["state"], text="Talca")
    assert "Salud Responde" in r["messages"][0]["text"]
