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


def test_triaje_rapido_nivel_alto_por_edad():
    r = turn({}, start=True, text="mi hijo tiene fiebre")
    assert r["state"]["step"] == "t_edad" and r["state"]["sintomas"] == ["fiebre"]
    r = turn(r["state"], option_id="ori:t:edad:0-5")
    r = turn(r["state"], option_id="ori:t:dur:lt24")
    r = turn(r["state"], option_id="ori:t:alarma:no")
    assert "Nivel ALTO" in r["messages"][0]["text"] and "no un diagnóstico" in r["messages"][0]["text"]
    assert r["events"][0]["props"]["nivel"] == "prioritario"


def test_triaje_rapido_bajo_y_medio():
    def flujo(sintomas, dur):
        r = turn({}, start=True)
        r = turn(r["state"], option_id="ori:t:edad:18-59")
        for s in sintomas:
            r = turn(r["state"], option_id=f"ori:t:sin:{s}")
        r = turn(r["state"], option_id="ori:t:sin:listo")
        r = turn(r["state"], option_id=f"ori:t:dur:{dur}")
        return turn(r["state"], option_id="ori:t:alarma:no")
    assert "Nivel BAJO" in flujo(["tos", "congestion"], "lt24")["messages"][0]["text"]
    assert "Nivel MEDIO" in flujo(["tos", "congestion", "fiebre"], "1-3")["messages"][0]["text"]
    assert "Nivel ALTO" in flujo(["tos"], "gt3")["messages"][0]["text"]


def test_triaje_alarma_muestra_tarjeta_de_emergencia():
    r = turn({"step": "t_alarma", "edad": "60+", "sintomas": ["fiebre"], "duracion": "1-3"},
             option_id="ori:t:alarma:si")
    assert "SAMU 131" in r["messages"][0]["text"] and r["events"][0]["props"]["nivel"] == "urgencia"


def test_chequeo_de_animo():
    r = turn({}, option_id="ori:animo")
    assert len(r["messages"][0]["options"]) == 4
    r = turn(r["state"], option_id="ori:animo:1")
    assert "4141" in r["messages"][0]["text"] and r["events"][0]["props"]["score"] == 1
    r = turn({}, option_id="ori:animo:3")
    assert "Respiración" in r["messages"][0]["text"]
    r = turn({}, option_id="ori:animo:agendar")
    assert r["handoff"]["entities"]["prestacion"] == "salud_mental"
