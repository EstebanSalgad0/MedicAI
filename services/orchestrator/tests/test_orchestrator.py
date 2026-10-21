import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import main, sessions  # noqa: E402
from medicai_common.contracts import DialogResponse, Handoff  # noqa: E402
from medicai_common.messages import text  # noqa: E402

emitted = []
main.events.emit = lambda t, **kw: emitted.append((t, kw))


def fake_service(service, req):
    if service == "medicamentos":
        return DialogResponse(messages=[text("ok farmacia")], state=None, resolved=True,
                              handoff=Handoff(service="recordatorios", entities={"medicamento": "X"}))
    if req.start:
        return DialogResponse(messages=[text(f"inicio {service}")], state={"step": 1})
    return DialogResponse(messages=[text(f"{service} recibió {req.text}")], state=None, resolved=True)


def msg(**kw):
    return main.InboundMessage(user_id="u1", **kw)


def setup_function():
    sessions.clear("u1")
    emitted.clear()


def test_texto_en_tramite_no_pasa_por_nlu():
    with patch.object(main, "call_service", fake_service), \
         patch.object(main, "nlu_parse", lambda t: {"intent": "recordatorio_medicamento", "confidence": .9,
                                                   "entities": {}, "source": "rasa", "latency_ms": 1}):
        main.process(msg(text="recuérdame algo"))
        with patch.object(main, "nlu_parse", side_effect=AssertionError("no debe consultarse")):
            r = main.process(msg(text="Losartán"))
    assert "recordatorios recibió Losartán" in r.messages[0].text
    types = [t for t, _ in emitted]
    assert "flow_started" in types and "flow_completed" in types


def test_alarma_antes_que_todo():
    r = main.process(msg(text="no puedo respirar"))
    assert "131" in r.messages[0].text and r.meta["red_flag"] == "urgencia"


def test_handoff_entre_servicios():
    with patch.object(main, "call_service", fake_service):
        r = main.process(msg(option_id="med:start"))
    assert [m.text for m in r.messages][:2] == ["ok farmacia", "inicio recordatorios"]
    assert sessions.load("u1")["service"] == "recordatorios"


def test_cancelar_interrumpe():
    with patch.object(main, "call_service", fake_service), \
         patch.object(main, "nlu_parse", lambda t: {"intent": "cancelar", "confidence": .9, "entities": {},
                                                   "source": "rasa", "latency_ms": 1}):
        main.process(msg(option_id="agd:start"))
        r = main.process(msg(text="cancelar"))
    assert "dejé ese trámite" in r.messages[0].text and not sessions.load("u1")
    assert any(t == "flow_abandoned" for t, _ in emitted)


def test_boton_menu_al_terminar_tramite():
    with patch.object(main, "call_service", fake_service), \
         patch.object(main, "nlu_parse", lambda t: {"intent": "recordatorio_medicamento", "confidence": .9,
                                                   "entities": {}, "source": "rasa", "latency_ms": 1}):
        r1 = main.process(msg(text="recuérdame algo"))
        r2 = main.process(msg(text="Losartán"))
    # en medio del trámite no se ofrece el menú; al terminar, sí
    assert all(o.id != "sys:menu" for m in r1.messages for o in m.options)
    assert any(o.id == "sys:menu" for o in r2.messages[-1].options)


def test_encuesta_registra_tramite_evaluado():
    sessions.store.delete("surveyed:u1")
    with patch.object(main, "call_service", fake_service):
        main.process(msg(option_id="agd:start"))
        r = main.process(msg(option_id="agd:x"))
        assert r.meta.get("survey_sent")
        r = main.process(msg(option_id="sys:survey:4"))
    survey = [kw for t, kw in emitted if t == "survey_response"]
    assert survey and survey[0]["props"] == {"rating": 4, "flow_service": "agendamiento"}
    assert any(o.id == "sys:menu" for o in r.messages[-1].options)


def test_boton_antiguo_no_es_error_tecnico():
    def falla(service, req):
        raise RuntimeError("estado vacío")
    with patch.object(main, "call_service", falla):
        r = main.process(msg(option_id="agd:confirm:yes"))
    assert "ya no está vigente" in r.messages[0].text
    assert r.messages[0].options[0].id == "sys:menu"
