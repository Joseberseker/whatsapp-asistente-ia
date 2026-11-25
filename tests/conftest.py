import hashlib
import hmac
import json

import pytest

from src import config


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "WHATSAPP_APP_SECRET", "secreto")
    monkeypatch.setattr(config, "WHATSAPP_VERIFY_TOKEN", "verificame")
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(config, "DASHBOARD_PASSWORD", "clave")


def sign(body: bytes) -> str:
    return "sha256=" + hmac.new(b"secreto", body, hashlib.sha256).hexdigest()


def inbound(text="hola", msg_id="wamid.1", wa_id="56911111111"):
    """Payload con la forma real que envía Meta."""
    return json.dumps({"object": "whatsapp_business_account", "entry": [{"id": "WABA", "changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp",
        "metadata": {"display_phone_number": "15550000000", "phone_number_id": "123"},
        "contacts": [{"profile": {"name": "Jose"}, "wa_id": wa_id}],
        "messages": [{"from": wa_id, "id": msg_id, "timestamp": "1764000000", "type": "text", "text": {"body": text}}],
    }}]}]}).encode()
