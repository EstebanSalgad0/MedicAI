import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

DB = Path(__file__).parent / "test_id.db"
DB.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{DB}"
os.environ["CLAVEUNICA_MODE"] = "demo"
os.environ["PUBLIC_BASE_URL"] = "https://medicai.test"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app import main  # noqa: E402
from medicai_common import auth  # noqa: E402

client = TestClient(main.app, follow_redirects=False)
client.__enter__()
sent = []
main.send = lambda to, msgs: sent.append((to, msgs)) or True


def ingresar(state: str, run: str, nombre: str):
    """Recorre el simulador de ClaveÚnica y devuelve la respuesta del callback."""
    r = client.get("/id/demo", params={"state": state})
    assert r.status_code == 200 and "Simulador de ClaveÚnica" in r.text
    r = client.post("/id/demo", data={"state": state, "run": run, "nombre": nombre})
    assert r.status_code == 303
    q = parse_qs(urlparse(r.headers["location"]).query)
    return client.get("/id/callback", params={"code": q["code"][0], "state": q["state"][0]})


def test_profesional_habilitado_recibe_token_con_rol_y_establecimientos():
    r = client.get("/id/login", params={"next": "/#ficha"})
    state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    r = ingresar(state, main._run(15111111), "Ana Rojas")
    assert r.status_code == 303
    destino, _, frag = r.headers["location"].partition("#token=")
    assert destino == "/#ficha"
    f = auth.leer(frag)
    assert f.rol == "medico" and f.metodo == "claveunica" and "hrt" in f.establecimientos
    # el enlace es de un solo uso
    assert client.get("/id/demo", params={"state": state}).status_code == 410


def test_run_no_habilitado_no_entra():
    r = client.get("/id/login")
    state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    r = ingresar(state, "11111111-1", "Otra Persona")
    assert r.status_code == 403 and "no está registrado" in r.text


def test_paciente_vincula_whatsapp_sin_dar_su_run_por_el_chat():
    sent.clear()
    r = client.post("/internal/solicitudes", json={"user_id": "56911", "proposito": "resultados"}).json()
    assert r["url"].startswith("https://medicai.test/id/vincular/")
    token = r["url"].rsplit("/", 1)[1]
    assert client.get("/internal/vinculos/56911").status_code == 404
    assert client.get(f"/id/vincular/{token}").status_code == 303
    r = ingresar(token, "12.345.678-5", "Juan Pérez Soto")
    assert r.status_code == 200 and "Identidad verificada" in r.text
    v = client.get("/internal/vinculos/56911").json()
    assert v["run"] == "12345678-5" and v["horas_desde_verificacion"] < 1
    assert sent[0][0] == "56911" and sent[0][1][0].options[0].id == "res:start"
    assert client.get("/internal/vinculos", params={"run": "12345678-5"}).json()["user_ids"] == ["56911"]


def test_cuidador_registra_persona_en_formulario_web():
    sent.clear()
    token = client.post("/internal/solicitudes", json={"user_id": "hija", "proposito": "cuidador"}).json()["url"]
    token = token.rsplit("/", 1)[1]
    r = ingresar(token, "12.345.678-5", "Camila Soto")
    assert "Modo cuidador" in r.text and 'name="run"' in r.text
    r = client.post("/id/cuidador", data={"token": token, "nombre": "Juan Soto", "run": "12.345.678-5",
                                          "relacion": "hijo", "declaro": "si"})
    assert "distinto al tuyo" in r.text
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"id": 7}
    with patch.object(main.httpx, "post", return_value=resp) as post:
        r = client.post("/id/cuidador", data={"token": token, "nombre": "Juan Soto", "run": "11.111.111-1",
                                              "relacion": "hijo", "declaro": "si"})
    assert "Registro listo" in r.text
    assert post.call_args.kwargs["json"]["patient_run"] == "11111111-1"
    assert sent[0][1][0].options[0].id == "ate:cui:act:7"


def test_enlace_vencido_o_inventado():
    assert client.get("/id/vincular/no-existe").status_code == 410


def test_admin_gestiona_profesionales():
    admin, _ = auth.emitir(auth.Funcionario(sub="admin", nombre="admin", rol="admin"))
    medico, _ = auth.emitir(auth.Funcionario(sub="x", nombre="x", rol="medico"))
    body = {"run": "11.111.111-1", "nombre": "Dr. Nuevo", "rol": "medico", "establecimientos": ["hrt"]}
    assert client.put("/profesionales", json=body, headers={"Authorization": f"Bearer {medico}"}).status_code == 403
    r = client.put("/profesionales", json=body, headers={"Authorization": f"Bearer {admin}"})
    assert r.status_code == 200 and r.json()["run"] == "11111111-1"
