import os
import sys
from pathlib import Path
from unittest.mock import patch

DB = Path(__file__).parent / "test_med.db"
DB.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{DB}"
os.environ["SEED_DEMO_STOCK"] = "true"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app import main  # noqa: E402

client = TestClient(main.app)
client.__enter__()


def turn(state, option_id=None, text="", start=False, intent=None):
    r = client.post("/dialog", json={"user_id": "569555", "text": text, "option_id": option_id,
                                     "state": state or {}, "start": start, "intent": intent})
    assert r.status_code == 200, r.text
    return r.json()


def test_programar_retiro_y_vincular_adherencia():
    r = turn({}, start=True)
    r = turn(r["state"], option_id="med:rx:yes")
    r = turn(r["state"], text="losartan")
    r = turn(r["state"], option_id="med:center:las_americas")
    assert "disponible" in r["messages"][0]["text"] and "Losartán 50 mg" in r["messages"][0]["text"]
    r = turn(r["state"], option_id="med:freq:30")
    r = turn(r["state"], text="hoy")
    r = turn(r["state"], option_id="med:hour:08:00")
    assert r["events"][0]["type"] == "pickup_scheduled"
    r = turn(r["state"], option_id="med:link:yes")
    assert r["handoff"]["service"] == "recordatorios"
    assert r["handoff"]["entities"]["medicamento"] == "Losartán 50 mg"

    sent = []
    with patch.object(main, "send", lambda u, m: sent.append(m) or True):
        main.tick()
    pick = [m for msgs in sent for m in msgs if m.options]
    if pick:  # depende de la hora en que corre el test
        r = turn({}, option_id=pick[0].options[0].id)
        assert r["events"][0]["type"] == "pickup_done"
        assert len(client.get("/pickups?status=pending").json()) == 1  # se creó el siguiente ciclo


def test_sin_stock_y_aviso_de_reposicion():
    r = turn({}, start=True)
    r = turn(r["state"], option_id="med:rx:yes")
    r = turn(r["state"], text="salbutamol")
    r = turn(r["state"], option_id="med:center:curico_centro")
    assert "no hay stock" in r["messages"][0]["text"]
    r = turn(r["state"], option_id="med:alert:yes")
    sent = []
    with patch.object(main, "send", lambda u, m: sent.append(m) or True):
        res = client.put("/stock", json={"center_id": "curico_centro", "name": "Salbutamol inhalador", "stock": 30})
    assert res.json()["notified"] == 1 and "Buenas noticias" in sent[0][0].text
