import hashlib
import hmac
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

os.environ.update(WHATSAPP_VERIFY_TOKEN="vt", WHATSAPP_APP_SECRET="secreto")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app import main  # noqa: E402
from app.whatsapp import to_payloads  # noqa: E402
from medicai_common.messages import Message, Option, lst  # noqa: E402

client = TestClient(main.app)

WEBHOOK = {"entry": [{"changes": [{"value": {
    "contacts": [{"wa_id": "56911112222", "profile": {"name": "Ana"}}],
    "messages": [{"id": "wamid.1", "from": "56911112222", "type": "interactive",
                  "interactive": {"type": "list_reply", "list_reply": {"id": "agd:start", "title": "Agendar"}}}],
}}]}]}


def signed(body):
    raw = json.dumps(body).encode()
    sig = "sha256=" + hmac.new(b"secreto", raw, hashlib.sha256).hexdigest()
    return raw, {"X-Hub-Signature-256": sig, "Content-Type": "application/json"}


def test_verificacion_webhook():
    ok = client.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "vt", "hub.challenge": "42"})
    assert ok.text == "42"
    assert client.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "x"}).status_code == 403


def test_firma_invalida_rechazada():
    raw, _ = signed(WEBHOOK)
    r = client.post("/webhook", content=raw, headers={"X-Hub-Signature-256": "sha256=malo"})
    assert r.status_code == 401


def test_webhook_deduplica_y_enruta_opcion():
    calls = []
    with patch.object(main, "handle_inbound", lambda item, t: calls.append(item)):
        raw, h = signed(WEBHOOK)
        assert client.post("/webhook", content=raw, headers=h).json()["queued"] == 1
        assert client.post("/webhook", content=raw, headers=h).json()["queued"] == 0  # reintento de Meta
    assert calls[0]["option_id"] == "agd:start" and calls[0]["name"] == "Ana"


def test_limites_de_whatsapp():
    m = lst("x" * 1500, [(f"id{i}", "Opción con un título demasiado largo " + str(i)) for i in range(12)])
    p = to_payloads("569", m)
    assert p[0]["type"] == "text" and p[1]["interactive"]["body"]["text"] == "Elige una opción:"
    rows = p[1]["interactive"]["action"]["sections"][0]["rows"]
    assert len(rows) == 10 and all(len(r["title"]) <= 24 for r in rows)
    b = to_payloads("569", Message(type="buttons", text="?", options=[Option(id="a", title="Un botón larguísimo de verdad")]))
    assert len(b[0]["interactive"]["action"]["buttons"][0]["reply"]["title"]) <= 20


def test_envio_interno_a_simulador_y_bandeja():
    r = client.post("/internal/send", json={"to": "web:abc", "messages": [{"type": "text", "text": "hola"}]})
    assert r.json()["sent"] == 1
    assert client.get("/outbox/web:abc").json()["messages"][0]["text"] == "hola"
    assert client.get("/outbox/web:abc").json()["messages"] == []


def test_proveedor_360dialog(monkeypatch):
    from app import providers
    monkeypatch.setenv("D360_API_KEY", "k123")
    monkeypatch.setenv("WHATSAPP_PROVIDER", "auto")
    p = providers.load()
    assert p.name == "360dialog" and p.configured
    assert p.send_url == "https://waba-v2.360dialog.io/messages" and p.headers == {"D360-API-KEY": "k123"}
    monkeypatch.delenv("D360_API_KEY")
    assert providers.load().name == "meta" and not providers.load().configured


def test_secreto_compartido_del_webhook(monkeypatch):
    from app.providers import Provider
    monkeypatch.setattr(main, "PROVIDER", Provider("360dialog", "https://x/messages", {}, True))
    monkeypatch.setattr(main, "WEBHOOK_SECRET", "s3cr3t")
    monkeypatch.setattr(main, "APP_SECRET", "")
    body = {"messages": [{"id": "wamid.flat", "from": "569", "type": "text", "text": {"body": "hola"}}],
            "contacts": [{"wa_id": "569", "profile": {"name": "Luis"}}]}
    assert client.post("/webhook", json=body).status_code == 401
    calls = []
    with patch.object(main, "handle_inbound", lambda item, t: calls.append(item)):
        r = client.post("/webhook", json=body, headers={"X-MedicAI-Webhook-Secret": "s3cr3t"})
    assert r.status_code == 200 and calls[0]["text"] == "hola" and calls[0]["name"] == "Luis"


def test_secreto_360dialog_no_afecta_a_meta(monkeypatch):
    monkeypatch.setattr(main, "WEBHOOK_SECRET", "s3cr3t")
    monkeypatch.setattr(main, "APP_SECRET", "")
    with patch.object(main, "handle_inbound", lambda item, t: None):
        assert client.post("/webhook", json=WEBHOOK).status_code == 200
