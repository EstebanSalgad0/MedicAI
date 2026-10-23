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


# ---------- derivaciones clínicas (Módulo 3) ----------
from medicai_common import auth  # noqa: E402

from app import derivaciones, dialog  # noqa: E402


def hdr(rol="medico", ests=("las_americas",)):
    t, _ = auth.emitir(auth.Funcionario(sub="15111111-1", nombre="Dra. Ana Rojas", rol=rol, run="15111111-1",
                                        establecimientos=list(ests), metodo="claveunica"))
    return {"Authorization": f"Bearer {t}"}


NUEVA = {"paciente_run": "12.345.678-5", "paciente_nombre": "Juan Pérez", "origen_id": "las_americas",
         "destino_id": "hrt", "especialidad": "Cardiología", "prioridad": "preferente", "motivo": "Disnea de esfuerzo"}


def test_derivacion_trazable_de_enviada_a_atendida():
    assert client.post("/derivaciones", json=NUEVA, headers=hdr(ests=("julio_contardo",))).status_code == 403
    d = client.post("/derivaciones", json=NUEVA, headers=hdr()).json()
    assert d["estado"] == "enviada" and d["red"] == "intra" and d["responsable"].startswith("Dra. Ana Rojas")
    assert d["folio"].startswith("DER-")
    # el destino la agenda (con fecha) y luego registra la atención
    some = hdr(rol="some", ests=("hrt",))
    assert client.patch(f"/derivaciones/{d['id']}", json={"estado": "agendada"}, headers=some).status_code == 422
    avisos = []
    with patch.object(derivaciones.identidad, "usuarios_de_run", lambda run: ["569444"]), \
         patch.object(derivaciones, "send", lambda u, m: avisos.append((u, m)) or True):
        r = client.patch(f"/derivaciones/{d['id']}", json={"estado": "agendada", "fecha_cita": "2026-11-20T10:00:00"},
                         headers=some)
    assert r.json()["estado"] == "agendada" and avisos and "Cardiología" in avisos[0][1][0].text
    r = client.patch(f"/derivaciones/{d['id']}", json={"estado": "atendida"}, headers=some)
    assert r.json()["estado"] == "atendida"
    r = client.patch(f"/derivaciones/{d['id']}", json={"estado": "caducada"}, headers=some)
    assert r.status_code == 409  # estado final
    items = client.get("/derivaciones", params={"run": "12345678-5"}, headers=some).json()["items"]
    ev = next(x for x in items if x["id"] == d["id"])["eventos"]
    assert [e["estado"] for e in ev] == ["enviada", "agendada", "atendida"] and all(e["responsable"] for e in ev)


def test_extra_red_activa_y_caducidad_por_plazo():
    d = client.post("/derivaciones", json={**NUEVA, "destino_id": "inst_torax", "especialidad": "Neumología"},
                    headers=hdr()).json()
    assert d["red"] == "extra"
    r = client.get("/internal/derivaciones/activas", params={"run": "12345678-5", "destinos": "inst_torax"})
    assert r.json()["activas"] >= 1
    with patch.object(derivaciones, "CADUCA_DIAS", -1), \
         patch.object(derivaciones.identidad, "usuarios_de_run", lambda run: []):
        assert derivaciones.caducar_vencidas() >= 1
    items = client.get("/derivaciones", params={"estado": "caducada"}, headers=hdr()).json()["items"]
    assert items and items[0]["eventos"][-1]["responsable"] == "Sistema (plazo vencido)"


def test_paciente_consulta_su_derivacion_con_claveunica():
    with patch.object(dialog.identidad, "vinculo", lambda u: None), \
         patch.object(dialog.identidad, "enlace", lambda u, p: ("https://medicai.test/id/vincular/z", 10)):
        r = turn({}, option_id="der:estado")
    assert "ClaveÚnica" in r["messages"][0]["text"]
    with patch.object(dialog.identidad, "vinculo", lambda u: {"run": "12345678-5", "horas_desde_verificacion": 1}):
        r = turn({}, option_id="der:estado")
    assert "Tus derivaciones" in r["messages"][0]["text"] and "Neumología" in r["messages"][0]["text"]
