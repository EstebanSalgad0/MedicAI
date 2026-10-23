import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

DB = Path(__file__).parent / "test_hist.db"
DB.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{DB}"
os.environ["LLM_PROVIDER"] = "none"
os.environ["DERIVACION_URL"] = "http://127.0.0.1:9"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app import dictado, fuentes, main  # noqa: E402
from medicai_common import auth  # noqa: E402

client = TestClient(main.app)
client.__enter__()
CASO = "12.345.678-5"


def token(rol="medico", ests=("las_americas", "hrt"), metodo="claveunica", run="15111111-1"):
    t, _ = auth.emitir(auth.Funcionario(sub=run, nombre="Dra. Ana Rojas", rol=rol, run=run,
                                        establecimientos=list(ests), metodo=metodo))
    return {"Authorization": f"Bearer {t}"}


def citas_validas(items):
    return all(i["cita"].startswith("[") and " · Exp. " in i["cita"] and i["cita"].endswith("]") for i in items)


def test_perfil_multi_establecimiento_con_citas_y_alertas():
    r = client.get(f"/pacientes/{CASO}/perfil", params={"establecimientos": "las_americas,hrt"}, headers=token())
    assert r.status_code == 200, r.text
    p = r.json()
    res = p["resumen"]
    assert p["paciente"]["nombre"] == "Juan Pérez Soto" and p["paciente"]["run_mask"] == "12.***.**8-5"
    # cada dato clínico lleva su cita y su establecimiento
    for grupo in (res["condiciones_activas"], res["medicamentos_vigentes"], res["alergias"], p["examenes"]):
        assert grupo and citas_validas(grupo)
    # la alergia está solo en el hospital: sin consulta multi-establecimiento se perdería
    assert res["alergias"][0]["establecimiento"] == "Hospital Regional de Talca"
    codigos = {a["codigo"] for a in p["alertas"]}
    assert {"INT-01", "INT-02", "RSG-01", "RSG-03", "CTL-01"} <= codigos
    assert all(a["citas"] for a in p["alertas"])
    hba1c = [e for e in p["examenes"] if "HbA1c" in e["nombre"]]
    assert hba1c[0]["estado"] == "alto" and hba1c[0]["fecha"] > hba1c[1]["fecha"]  # cronológico
    assert {f["estado"] for f in p["fuentes"]} == {"ok"}


def test_dato_faltante_se_informa_y_no_se_inventa():
    r = client.get(f"/pacientes/{CASO}/perfil", params={"establecimientos": "las_americas"}, headers=token())
    res = r.json()["resumen"]
    assert res["alergias"] == []
    assert any("No se encontró registro de alergias en las fuentes disponibles" in f for f in res["faltantes"])


def test_sin_relacion_asistencial_se_deniega_y_queda_auditado():
    h = token(ests=("armando_williams",), run="17333333-5")
    r = client.get(f"/pacientes/{CASO}/perfil", headers=h)
    assert r.status_code == 403 and "relación asistencial" in r.json()["detail"]
    r = client.get(f"/pacientes/{CASO}/perfil", params={"motivo": "urgencia"}, headers=h)
    assert r.status_code == 200
    admin = token(rol="admin", metodo="local")
    log = client.get("/auditoria", params={"run": CASO}, headers=admin).json()
    assert {"denegado", "excepcional_urgencia"} <= {a["resultado"] for a in log}


def test_roles_no_clinicos_y_cuentas_locales_no_ven_fichas():
    assert client.get(f"/pacientes/{CASO}/perfil", headers=token(rol="some")).status_code == 403
    assert client.get(f"/pacientes/{CASO}/perfil", headers=token(metodo="local")).status_code == 403
    assert client.get(f"/pacientes/{CASO}/perfil").status_code == 401
    assert client.get("/pacientes/12.345.678-9/perfil", headers=token()).status_code == 422


def test_stream_informa_progreso_por_base():
    with client.stream("GET", f"/pacientes/{CASO}/perfil/stream", headers=token(),
                       params={"establecimientos": "las_americas,hrt,julio_contardo"}) as r:
        lineas = [json.loads(x) for x in r.iter_lines() if x]
    assert lineas[0]["evento"] == "inicio"
    fuentes_ev = [x for x in lineas if x["evento"] == "fuente"]
    assert {x["id"] for x in fuentes_ev} == {"las_americas", "hrt", "julio_contardo"}
    assert next(x for x in fuentes_ev if x["id"] == "julio_contardo")["estado"] == "sin_registros"
    assert lineas[-1]["evento"] == "perfil" and lineas[-1]["perfil"]["alertas"]


def test_base_lenta_se_informa_sin_bloquear():
    lento = fuentes._demo

    def demora(run, est):
        if est == "hrt":
            import time
            time.sleep(1.5)
        return lento(run, est)

    with patch.object(fuentes, "_demo", demora):
        res = {r.establecimiento_id: r for r in fuentes.consultar("12345678-5", ["las_americas", "hrt"], timeout=0.8)}
    assert res["las_americas"].estado == "ok" and res["hrt"].estado == "tiempo_agotado"


def test_apoyo_diagnostico_con_fuentes_y_sin_diagnostico_cerrado():
    r = client.post(f"/pacientes/{CASO}/apoyo", headers=token(),
                    json={"cuadro": "Consulta por edema de extremidades y disnea de esfuerzo"})
    h = r.json()["hipotesis"]
    dx = next(x for x in h if x["codigo"] == "DX-02")
    assert dx["hipotesis"].startswith("Hipótesis a considerar") and "confirmación del médico" in dx["nota"]
    assert any("Ecocardiograma" in f["texto"] for f in dx["fundamentos"]) and dx["examenes_sugeridos"]
    r = client.post(f"/pacientes/{CASO}/apoyo", headers=token(), json={"cuadro": "control sin molestias"})
    assert r.json()["hipotesis"] == [] and "No se encontraron hipótesis" in r.json()["sin_resultados"]


def test_dictado_ordena_sin_agregar_texto():
    texto = ("Paciente consulta por cefalea de 3 días. Refiere mal adherencia a losartán. "
             "Al examen: presión arterial 160/95, lúcido. Diagnóstico: hipertensión no controlada. "
             "Indicaciones: control en 2 semanas y retomar tratamiento.")
    out = dictado.estructurar(texto)
    sec = {s["id"]: s for s in out["secciones"]}
    assert "cefalea" in sec["anamnesis"]["texto"] and "160/95" in sec["examen_fisico"]["texto"]
    assert "hipertensión no controlada" in sec["diagnostico"]["texto"]
    assert "control en 2 semanas" in sec["indicaciones"]["texto"]
    assert out["estado"] == "borrador"
    vacio = {s["id"]: s for s in dictado.estructurar("Paciente refiere dolor lumbar.")["secciones"]}
    assert vacio["diagnostico"]["texto"] == "" and "No se dictó" in vacio["diagnostico"]["faltante"]


def test_modelo_que_inventa_texto_se_descarta():
    with patch.object(dictado.llm, "complete", lambda *a, **k: json.dumps(
            {"anamnesis": "Paciente con fiebre alta", "examen_fisico": "", "diagnostico": "Neumonía",
             "indicaciones": ""})):
        assert dictado.por_modelo("Paciente refiere dolor lumbar.") is None


def test_ficha_borrador_firma_e_inmutable():
    h = token()
    body = {"paciente_run": CASO, "establecimiento_id": "las_americas", "transcripcion": "x",
            "secciones": [{"id": "anamnesis", "texto": "Dolor lumbar"}, {"id": "indicaciones", "texto": "Reposo"}]}
    assert client.post("/fichas", json={**body, "establecimiento_id": "curico_centro"}, headers=h).status_code == 403
    f = client.post("/fichas", json=body, headers=h).json()
    assert f["estado"] == "borrador"
    assert client.post(f"/fichas/{f['id']}/firmar", headers=h).json()["estado"] == "firmada"
    assert client.put(f"/fichas/{f['id']}", json=body, headers=h).status_code == 409
    assert client.post("/fichas/transcribir", files={"audio": ("a.webm", b"x")}, headers=h).status_code == 503


def test_controles_sugeridos_para_el_chat_sin_diagnosticos():
    c = client.get("/internal/controles-sugeridos/12345678-5").json()["controles"]
    assert {x["prestacion"] for x in c} == {"control_cronico", "vacunacion"}
    assert all("diabetes" not in x["motivo"].lower() for x in c)
