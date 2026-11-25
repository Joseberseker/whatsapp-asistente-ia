"""Persistencia en SQLite: contactos, mensajes, ids procesados."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from . import config

MAX_HISTORY = 20
WINDOW = timedelta(hours=24)  # ventana de servicio de WhatsApp

_SCHEMA = """
CREATE TABLE IF NOT EXISTS contacts (
    wa_id TEXT PRIMARY KEY, name TEXT, last_inbound_at TEXT
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT, wa_id TEXT NOT NULL, role TEXT NOT NULL,
    content TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_wa ON messages(wa_id);
CREATE TABLE IF NOT EXISTS processed (msg_id TEXT PRIMARY KEY);
"""


def now() -> datetime:
    return datetime.now(timezone.utc)


@contextmanager
def connect():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def first_time(msg_id: str) -> bool:
    """True solo la primera vez que vemos este id (Meta puede reenviar el mismo webhook)."""
    with connect() as c:
        return c.execute("INSERT OR IGNORE INTO processed (msg_id) VALUES (?)", (msg_id,)).rowcount == 1


def record_inbound(wa_id: str, name: str, text: str) -> None:
    ts = now().isoformat()
    with connect() as c:
        c.execute(
            "INSERT INTO contacts (wa_id, name, last_inbound_at) VALUES (?, ?, ?) "
            "ON CONFLICT(wa_id) DO UPDATE SET name = excluded.name, last_inbound_at = excluded.last_inbound_at",
            (wa_id, name, ts),
        )
        c.execute("INSERT INTO messages (wa_id, role, content, created_at) VALUES (?, 'user', ?, ?)", (wa_id, text, ts))


def record_outbound(wa_id: str, text: str) -> None:
    with connect() as c:
        c.execute("INSERT INTO messages (wa_id, role, content, created_at) VALUES (?, 'assistant', ?, ?)",
                  (wa_id, text, now().isoformat()))


def history(wa_id: str, limit: int = MAX_HISTORY) -> list[dict]:
    with connect() as c:
        rows = c.execute("SELECT role, content FROM messages WHERE wa_id = ? ORDER BY id DESC LIMIT ?", (wa_id, limit)).fetchall()
    return [dict(r) for r in reversed(rows)]


def in_window(wa_id: str, at: datetime | None = None) -> bool:
    """¿Podemos mandar texto libre? Solo si el usuario escribió en las últimas 24 h."""
    with connect() as c:
        row = c.execute("SELECT last_inbound_at FROM contacts WHERE wa_id = ?", (wa_id,)).fetchone()
    if not row or not row["last_inbound_at"]:
        return False
    return (at or now()) - datetime.fromisoformat(row["last_inbound_at"]) < WINDOW
