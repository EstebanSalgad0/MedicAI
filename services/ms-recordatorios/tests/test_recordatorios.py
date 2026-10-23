import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

DB = Path(__file__).parent / "test_rec.db"
DB.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{DB}"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app import dialog, main  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
client.__enter__()


def turn(state, option_id=None, text="", start=False, intent=None, entities=None):
    r = client.post("/dialog", json={"user_id": "569222", "text": text, "option_id": option_id,
                                     "state": state or {}, "start": start, "intent": intent,
                                     "entities": entities or {}})
    assert r.status_code == 200, r.text
    return r.json()


def test_spread():
    assert dialog.spread("08:00", 2) == ["08:00", "20:00"]
    assert dialog.spread("06:00", 3) == ["06:00", "14:00", "22:00"]


def test_crear_recordatorio_y_registrar_toma():
    r = turn({}, start=True, intent="recordatorio_medicamento")
    r = turn(r["state"], text="losartán 50 mg")
    assert r["state"]["medication"] == "Losartán 50 mg" and r["state"]["step"] == "dose"
    r = turn(r["state"], option_id="rec:dose_q:1 comprimido")
    r = turn(r["state"], option_id="rec:freq:2")
    r = turn(r["state"], text="a las 8:00")
    assert r["state"]["times"] == ["08:00", "20:00"] and r["state"]["step"] == "rx"
    r = turn(r["state"], text="25-10-2026")
    assert r["state"]["rx_end"] == "2026-10-25" and "minutos antes" in r["messages"][0]["text"]
    r = turn(r["state"], option_id="rec:save:yes")
    assert r["resolved"] and r["events"][0]["type"] == "reminder_created"

    sent = []
    # el aviso llega 10 minutos antes de la toma de las 08:00
    fake_now = datetime(2026, 10, 21, 7, 52, tzinfo=dialog.now_local().tzinfo)
    with patch.object(main, "send", lambda u, m: sent.append(m) or True),          patch.object(main, "now_local", lambda: fake_now):
        result = main.tick()
        assert result["sent"] == 1 and result["rx_renewal"] == 0  # antes de las 9 no se avisa la receta
        assert main.tick()["sent"] == 0  # no duplica
    assert "(1 comprimido)" in sent[0][0].text
    dose_opt = sent[0][0].options[0].id
    r = turn({}, option_id=dose_opt)
    assert r["events"][0]["type"] == "dose_taken"
    assert client.get("/stats").json()["totals"]["taken"] == 1

    # receta que termina en 4 días: aviso de renovación
    with patch.object(main, "send", lambda u, m: sent.append(m) or True),          patch.object(main, "now_local", lambda: fake_now.replace(hour=10)):
        assert main.tick()["rx_renewal"] == 1
        assert main.tick()["rx_renewal"] == 0
    assert "termina el 25-10-2026" in sent[-1][0].text


def test_handoff_con_medicamento():
    r = turn({}, start=True, entities={"medicamento": "metformina", "source": "medicamentos"})
    assert r["state"]["step"] == "dose" and r["state"]["source"] == "medicamentos"
