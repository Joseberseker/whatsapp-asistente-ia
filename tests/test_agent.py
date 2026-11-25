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


def test_falls_back_to_second_model(monkeypatch):
    from types import SimpleNamespace
    from tests.fakes import text as text_resp
    tried = []

    def gen(model, contents, config):
        tried.append(model)
        if model == "principal":
            raise RuntimeError("429 RESOURCE_EXHAUSTED")
        return text_resp("respaldo ok")
    monkeypatch.setattr(agent, "_client", SimpleNamespace(models=SimpleNamespace(generate_content=gen)))
    monkeypatch.setattr(agent.config, "GEMINI_MODEL", "principal")
    monkeypatch.setattr(agent.config, "GEMINI_FALLBACK_MODELS", "respaldo")
    store.record_inbound("569", "Jose", "hola")
    assert agent.reply("569") == "respaldo ok"
    assert tried == ["principal", "respaldo"]
