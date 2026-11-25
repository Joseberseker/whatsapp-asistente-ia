import json

from fastapi.testclient import TestClient

from src import app as app_module, whatsapp
from tests.conftest import inbound, sign

client = TestClient(app_module.app)


def test_signature():
    body = inbound()
    assert whatsapp.valid_signature(body, sign(body))
    assert not whatsapp.valid_signature(body, sign(b"otro"))
    assert not whatsapp.valid_signature(body, None)


def test_parse_ignores_statuses():
    msgs = whatsapp.parse_messages(json.loads(inbound("hola")))
    assert msgs == [{"id": "wamid.1", "from": "56911111111", "name": "Jose", "type": "text", "text": "hola"}]
    status = {"entry": [{"changes": [{"value": {"statuses": [{"id": "x", "status": "read"}]}}]}]}
    assert whatsapp.parse_messages(status) == []


def test_verify_handshake():
    ok = client.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "verificame", "hub.challenge": "42"})
    assert ok.status_code == 200 and ok.text == "42"
    assert client.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "mal"}).status_code == 403


def test_post_rejects_bad_signature():
    assert client.post("/webhook", content=inbound(), headers={"X-Hub-Signature-256": "sha256=00"}).status_code == 401


def test_post_dispatches_message(monkeypatch):
    seen = []
    monkeypatch.setattr(app_module, "handle_message", seen.append)
    body = inbound("hola")
    assert client.post("/webhook", content=body, headers={"X-Hub-Signature-256": sign(body)}).status_code == 200
    assert seen[0]["text"] == "hola"


def test_message_marks_read_typing_and_replies(monkeypatch):
    calls = []
    monkeypatch.setattr(whatsapp, "_post", lambda payload: calls.append(payload) or {})
    monkeypatch.setattr(app_module.agent, "reply", lambda wa_id: "¡Hola!")
    msg = whatsapp.parse_messages(json.loads(inbound("hola", msg_id="wamid.T")))[0]
    app_module.handle_message(msg)
    assert calls[0] == {"status": "read", "message_id": "wamid.T", "typing_indicator": {"type": "text"}}
    assert calls[1]["text"] == {"body": "¡Hola!"}


def test_typing_failure_does_not_block_reply(monkeypatch):
    sent = []
    monkeypatch.setattr(whatsapp, "mark_read_typing", lambda mid: 1 / 0)
    monkeypatch.setattr(whatsapp, "send_text", lambda to, body: sent.append(body))
    monkeypatch.setattr(app_module.agent, "reply", lambda wa_id: "ok")
    app_module.handle_message(whatsapp.parse_messages(json.loads(inbound(msg_id="wamid.U")))[0])
    assert sent == ["ok"]
