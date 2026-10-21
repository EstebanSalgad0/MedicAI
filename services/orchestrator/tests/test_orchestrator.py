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
