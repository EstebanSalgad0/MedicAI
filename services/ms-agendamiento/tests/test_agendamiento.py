import os
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(__file__).parent / "test_agd.db")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
Path(__file__).parent.joinpath("test_agd.db").unlink(missing_ok=True)

from fastapi.testclient import TestClient  # noqa: E402

from app import gap  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
client.__enter__()  # dispara startup
sent = []
gap.send = lambda to, msgs: sent.append((to, msgs)) or True  # avisos proactivos sin gateway


def turn(state, option_id=None, text="", start=False, intent=None, user="569111", entities=None):
    r = client.post("/dialog", json={"user_id": user, "name": "Ana", "text": text, "option_id": option_id,
                                     "state": state or {}, "start": start, "intent": intent,
                                     "entities": entities or {}})
    assert r.status_code == 200, r.text
    return r.json()


def test_reserva_cesfam_completa_y_cancelacion():
    r = turn({}, start=True, intent="agendar_cita")
    assert [o["id"] for o in r["messages"][0]["options"]] == ["agd:place:hrt", "agd:place:cesfam"]
    r = turn(r["state"], option_id="agd:place:cesfam")
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
    assert "APS-" in r["messages"][0]["text"]

    # el cupo ya no se ofrece
    r = turn({}, option_id="agd:place:cesfam")
    r = turn(r["state"], option_id="agd:esp:odontologia")
    r = turn(r["state"], option_id="agd:center:las_americas")
    assert slot_opt not in [o["id"] for o in r["messages"][0]["options"]]

    appts = client.get("/appointments").json()
    assert len(appts) == 1
    r = turn({}, option_id=f"agd:cancel:{appts[0]['id']}")
    assert r["events"][0]["type"] == "appointment_cancelled"
    assert r["messages"][0]["options"][0]["id"].startswith("agd:wl:join:")  # ofrece lista de espera
    assert client.get("/appointments").json()[0]["status"] == "cancelled"


def test_hospital_con_interconsulta_y_codigo():
    r = turn({}, start=True, intent="agendar_cita", text="me diagnosticaron cataratas",
             entities={"prestacion": "oftalmologia"})
    assert r["state"]["step"] == "deriv" and r["state"]["ges"] == "cataratas"
    r = turn(r["state"], option_id="agd:deriv:yes")
    days = [o["id"] for o in r["messages"][0]["options"]]
    assert days == ["agd:day:hoy", "agd:day:manana", "agd:day:semana", "agd:day:proxima"]
    r = turn(r["state"], option_id="agd:day:proxima")
    assert len([o for o in r["messages"][0]["options"] if o["id"].startswith("agd:slot:")]) == 5
    r = turn(r["state"], option_id=r["messages"][0]["options"][0]["id"])
    assert "garantía GES" in r["messages"][0]["text"]
    r = turn(r["state"], option_id="agd:confirm:yes")
    assert "HRT-" in r["messages"][0]["text"] and "48 h y 24 h" in r["messages"][0]["text"]


def test_sin_interconsulta_explica_como_obtenerla():
    r = turn({}, option_id="agd:place:hrt")
    r = turn(r["state"], option_id="agd:hesp:cardiologia")
    r = turn(r["state"], option_id="agd:deriv:no")
    assert "interconsulta" in r["messages"][0]["text"].lower() and r["state"] is None
    assert r["events"][0]["type"] == "referral_required"


def test_fill_the_gap_ofrece_cupo_liberado():
    sent.clear()
    # Paciente A toma una hora; paciente B queda en lista de espera de lo mismo
    r = turn({}, option_id="agd:place:hrt", user="A")
    r = turn(r["state"], option_id="agd:hesp:kinesiologia", user="A")
    r = turn(r["state"], option_id="agd:day:proxima", user="A")
    r = turn(r["state"], option_id=r["messages"][0]["options"][0]["id"], user="A")
    r = turn(r["state"], option_id="agd:confirm:yes", user="A")
    r = turn({}, option_id="agd:wl:join:hrt:kinesiologia", user="B")
    assert "lista de espera" in r["messages"][0]["text"]

    # A cancela: el cupo se ofrece a B
    a_id = [a for a in client.get("/appointments").json() if a["prestacion"] == "kinesiologia"][0]["id"]
    turn({}, option_id=f"agd:cancel:{a_id}", user="A")
    assert sent and sent[-1][0] == "B"
    offer_btn = sent[-1][1][0]["options"][0]["id"] if isinstance(sent[-1][1][0], dict) \
        else sent[-1][1][0].options[0].id
    r = turn({}, option_id=offer_btn, user="B")
    assert [e["type"] for e in r["events"]] == ["gap_filled", "appointment_booked"]
    stats = client.get("/stats/daily", params={"days": 3}).json()
    assert sum(d["gap_filled"] for d in stats) == 1


def test_mis_citas_vacio():
    r = turn({}, start=True, intent="ver_citas", user="nadie")
    assert "No tienes horas" in r["messages"][0]["text"]


def test_boton_confirmar_antiguo_no_falla():
    r = turn({}, option_id="agd:confirm:yes")  # trámite ya cerrado: llega sin estado
    assert "ya no está vigente" in r["messages"][0]["text"] and r["state"] is None


# ---------- Módulo 3: agenda centralizada y prioridad clínica ----------
from datetime import datetime, timedelta  # noqa: E402
from unittest.mock import patch  # noqa: E402

from app import dialog as agd_dialog  # noqa: E402
from app.models import SessionLocal, Waitlist  # noqa: E402
from medicai_common import auth  # noqa: E402


def hdr(rol="some"):
    t, _ = auth.emitir(auth.Funcionario(sub="x", nombre="Luis Pino", rol=rol, establecimientos=["las_americas"]))
    return {"Authorization": f"Bearer {t}"}


def test_ocupacion_por_box_y_profesional():
    r = turn({}, option_id="agd:place:cesfam", user="569900")
    r = turn(r["state"], option_id="agd:esp:medicina_general", user="569900")
    r = turn(r["state"], option_id="agd:center:las_americas", user="569900")
    slot = r["messages"][0]["options"][1]["id"].split(":", 2)[2]
    r = turn(r["state"], option_id=f"agd:slot:{slot}", user="569900")
    turn(r["state"], option_id="agd:confirm:yes", user="569900")
    o = client.get("/ocupacion", params={"center_id": "las_americas", "fecha": slot[:10]}).json()
    fila = next(f for f in o["filas"] if f["prestacion"] == "medicina_general")
    assert fila["profesional"] and fila["box"].startswith("Box")
    assert next(s for s in fila["slots"] if s["hora"] == slot[11:16])["estado"] == "ocupada"
    assert o["resumen"]["usados"] >= 1
    assert len(o["filas"]) == len(client.get("/catalog").json()["dotacion"]["las_americas"])


def test_prioridad_clinica_prevalece_y_se_explica():
    with SessionLocal() as db:
        db.add_all([Waitlist(user_id="antiguo", center_id="las_americas", prestacion="nutricion", priority=0,
                             created_at=datetime(2026, 1, 1)),
                    Waitlist(user_id="nuevo", center_id="las_americas", prestacion="nutricion", priority=0,
                             created_at=datetime(2026, 3, 1))])
        db.commit()
    w = [x for x in client.get("/waitlist").json() if x["prestacion"] == "nutricion"]
    nuevo = next(x for x in w if str(x["created_at"]).startswith("2026-03"))
    assert client.patch(f"/waitlist/{nuevo['id']}", json={"priority": 2}, headers=hdr()).status_code == 422
    r = client.patch(f"/waitlist/{nuevo['id']}", json={"priority": 2, "motivo": "Desnutrición en adulto mayor"},
                     headers=hdr())
    assert r.json()["priority_by"].startswith("Luis Pino")
    sent.clear()
    dia = datetime.now().date() + timedelta(days=3)
    while dia.weekday() >= 5:
        dia += timedelta(days=1)
    assert gap.offer_gap("las_americas", "nutricion", datetime(dia.year, dia.month, dia.day, 9, 30))
    assert sent[0][0] == "nuevo"
    oferta = client.get("/gap-offers").json()[0]
    assert "Prioridad clínica" in oferta["criterio"] and "orden de llegada" in oferta["criterio"]
    assert "Desnutrición" in oferta["criterio"]


def test_controles_sugeridos_segun_perfil():
    sug = [{"prestacion": "control_cronico", "motivo": "Tienes un control crónico pendiente"}]
    with patch.object(agd_dialog.perfil, "sugeridos", lambda u: sug):
        r = turn({}, option_id="agd:place:cesfam", user="569901")
    m = r["messages"][0]
    assert "Según tu ficha" in m["text"] and m["options"][0]["id"] == "agd:esp:control_cronico"
    assert "pendiente" in m["options"][0]["description"]
