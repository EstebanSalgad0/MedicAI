import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import llm, main  # noqa: E402


def fake_rasa(name, conf):
    return lambda text: {"intent": {"name": name, "confidence": conf},
                         "entities": [{"entity": "medicamento", "value": "losartán"}]}


def test_rasa_con_confianza_alta():
    with patch.object(main, "rasa_parse", fake_rasa("recordatorio_medicamento", 0.93)):
        r = main.parse("recuérdame el losartán")
    assert (r.intent, r.source, r.entities["medicamento"]) == ("recordatorio_medicamento", "rasa", "losartán")


def test_rasa_duda_y_responde_llm():
    with patch.object(main, "rasa_parse", fake_rasa("saludo", 0.31)), \
         patch.object(llm, "classify", lambda t: {"intent": "farmacia", "confidence": 0.8, "entities": {}}):
        r = main.parse("llegaron las pastillas de la presión?")
    assert (r.intent, r.source, r.rasa_intent) == ("farmacia", "llm", "saludo")


def test_modo_degradado_sin_rasa_ni_llm():
    with patch.object(main, "rasa_parse", lambda t: None), patch.object(llm, "classify", lambda t: None):
        assert main.parse("quiero pedir hora").intent == "agendar_cita"
        assert main.parse("mis citas").intent == "ver_citas"
        assert main.parse("xyzzy").source == "fallback"


def test_bandera_roja_no_depende_de_modelos():
    with patch.object(main, "rasa_parse", lambda t: (_ for _ in ()).throw(AssertionError("no debe llamarse"))):
        assert main.parse("no puedo respirar").intent == "emergencia"


def test_redaccion_de_datos_personales():
    out = llm.redact("soy 12.345.678-9, mi fono +56 9 1234 5678 y correo ana@mail.cl")
    assert "12.345" not in out and "1234" not in out and "ana@" not in out


def test_nlu_yml_valido_y_cubre_catalogo():
    import yaml
    base = Path(__file__).resolve().parents[2] / "nlu-rasa"
    data = yaml.safe_load((base / "data" / "nlu.yml").read_text())
    intents = {b["intent"] for b in data["nlu"] if "intent" in b}
    from app.intents import INTENTS
    assert intents == set(INTENTS)
    test = yaml.safe_load((base / "tests" / "test_nlu.yml").read_text())
    assert {b["intent"] for b in test["nlu"]} <= set(INTENTS)
