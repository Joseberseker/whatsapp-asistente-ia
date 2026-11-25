from fastapi.testclient import TestClient

from src import app as app_module, config, store
from src.modules import reminders
from tests.test_reminders import _future

client = TestClient(app_module.app)


def test_requires_auth(monkeypatch):
    assert client.get("/dashboard").status_code == 401
    assert client.get("/dashboard", auth=("admin", "mal")).status_code == 401
    monkeypatch.setattr(config, "DASHBOARD_PASSWORD", "")
    assert client.get("/dashboard", auth=("admin", "")).status_code == 401  # sin clave configurada, cerrado


def test_renders_data():
    store.record_inbound("569", "Jose", "hola bot")
    reminders.create("569", "tomar agua", _future())
    page = client.get("/dashboard", auth=("admin", "clave"))
    assert page.status_code == 200 and "Jose" in page.text and "tomar agua" in page.text
    assert client.get("/dashboard/parcial", auth=("admin", "clave")).status_code == 200
    chat = client.get("/dashboard/chat/569", auth=("admin", "clave"))
    assert "hola bot" in chat.text and "ventana 24 h abierta" in chat.text
    assert client.get("/dashboard/chat/000", auth=("admin", "clave")).status_code == 404
