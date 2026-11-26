from datetime import timedelta

from src import config, store, whatsapp
from src.modules import reminders


def _future(minutes=5):
    return (store.now() + timedelta(minutes=minutes)).astimezone(config.TZ).strftime("%Y-%m-%dT%H:%M:%S")


def _sent(monkeypatch):
    sent = []
    monkeypatch.setattr(whatsapp, "send_text", lambda to, body: sent.append(("text", to, body)))
    monkeypatch.setattr(whatsapp, "send_template", lambda to, name, lang, params: sent.append(("template", to, params)))
    return sent


def test_create_list_cancel():
    assert "Error" in reminders.create("569", "x", "mañana")
    assert "ya pasó" in reminders.create("569", "x", "2000-01-01T09:00")
    assert "#1 creado" in reminders.create("569", "tomar agua", _future())
    assert "tomar agua" in reminders.list_pending("569")
    assert reminders.list_pending("otro") == "No hay recordatorios pendientes."
    assert "No encontré" in reminders.cancel("otro", 1)  # no se puede cancelar el de otro contacto
    assert "cancelado" in reminders.cancel("569", 1)
    assert reminders.list_pending("569") == "No hay recordatorios pendientes."


def test_send_due_uses_text_inside_window(monkeypatch):
    sent = _sent(monkeypatch)
    store.record_inbound("569", "Jose", "hola")
    reminders.create("569", "tomar agua", _future(1))
    assert reminders.send_due() == 0
    monkeypatch.setattr(store, "now", lambda: reminders.datetime.now(reminders.timezone.utc) + timedelta(minutes=2))
    assert reminders.send_due() == 1
    assert sent == [("text", "569", "⏰ Recordatorio: tomar agua")]
    assert reminders.send_due() == 0  # no se reenvía


def test_send_due_uses_template_outside_window_and_marks_failures(monkeypatch):
    sent = _sent(monkeypatch)
    reminders.create("570", "pagar luz", _future(1))
    reminders.create("570", "falla", _future(1))

    def tpl(to, name, lang, params):
        if params == ["falla"]:
            raise RuntimeError("plantilla no aprobada")
        sent.append(("template", to, params))
    monkeypatch.setattr(whatsapp, "send_template", tpl)
    monkeypatch.setattr(store, "now", lambda: reminders.datetime.now(reminders.timezone.utc) + timedelta(minutes=2))
    assert reminders.send_due() == 2
    assert sent == [("template", "570", ["pagar luz"])]
    with store.connect() as c:
        assert [r[0] for r in c.execute("SELECT status FROM reminders ORDER BY id")] == ["sent", "failed"]


def test_relative_minutes_computed_in_code():
    # "en 3 minutos" no depende de que la IA sume bien la hora
    before = store.now()
    assert "creado" in reminders.create("569", "comer", en_minutos=3)
    with store.connect() as c:
        due = reminders.datetime.fromisoformat(c.execute("SELECT due_at FROM reminders").fetchone()[0])
    assert timedelta(minutes=2, seconds=59) <= due - before.replace(microsecond=0) <= timedelta(minutes=3, seconds=1)


def test_past_error_tells_model_the_current_time():
    msg = reminders.create("569", "x", fecha_hora="2000-01-01T09:00")
    assert "ya pasó" in msg and store.now().astimezone(config.TZ).strftime("%H:%M") in msg


def test_requires_some_time():
    assert "Error" in reminders.create("569", "x")
