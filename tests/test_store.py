from datetime import timedelta

from src import store


def test_dedupe():
    assert store.first_time("wamid.1")
    assert not store.first_time("wamid.1")


def test_history_and_window():
    assert not store.in_window("569")
    store.record_inbound("569", "Jose", "hola")
    store.record_outbound("569", "¡hola!")
    assert store.history("569") == [{"role": "user", "content": "hola"}, {"role": "assistant", "content": "¡hola!"}]
    assert store.in_window("569")
    assert not store.in_window("569", at=store.now() + timedelta(hours=25))
