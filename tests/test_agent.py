from src import agent, modules, store
from tests.fakes import call, scripted, text


def test_plain_reply_uses_history(monkeypatch):
    store.record_inbound("569", "Jose", "hola")
    seen = scripted(monkeypatch, text("¡Hola Jose!"))
    assert agent.reply("569") == "¡Hola Jose!"
    assert seen[0][0].parts[0].text == "hola"


def test_tool_call_roundtrip(monkeypatch):
    monkeypatch.setitem(modules.HANDLERS, "sumar", lambda wa_id, a, b: str(a + b))
    store.record_inbound("569", "Jose", "suma 2 y 3")
    seen = scripted(monkeypatch, call("sumar", a=2, b=3), text("Da 5"))
    assert agent.reply("569") == "Da 5"
    assert seen[1][-1].parts[0].function_response.response == {"result": "5"}


def test_unknown_tool_and_errors_go_back_to_model(monkeypatch):
    def boom(wa_id):
        raise ValueError("fecha inválida")
    monkeypatch.setitem(modules.HANDLERS, "boom", boom)
    store.record_inbound("569", "Jose", "x")
    seen = scripted(monkeypatch, call("nope"), call("boom"), text("ok"))
    agent.reply("569")
    assert "no existe" in seen[1][-1].parts[0].function_response.response["result"]
    assert "fecha inválida" in seen[2][-1].parts[0].function_response.response["result"]
