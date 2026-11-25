"""Módulo de recordatorios: la IA los crea, lista y cancela; un loop los envía al vencer."""

import asyncio
import logging
from datetime import datetime, timezone

from .. import config, store, whatsapp

log = logging.getLogger("asistente.reminders")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT, wa_id TEXT NOT NULL, text TEXT NOT NULL,
    due_at TEXT NOT NULL, created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | sent | failed | cancelled
    sent_at TEXT
);
"""


def _iso(dt: datetime) -> str:
    # mismo formato siempre (UTC, segundos) para poder comparar como texto en SQL
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def _local(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone(config.TZ).strftime("%d/%m %H:%M")


def create(wa_id: str, texto: str, fecha_hora: str) -> str:
    try:
        due = datetime.fromisoformat(fecha_hora)
    except ValueError:
        return f"Error: fecha_hora '{fecha_hora}' no tiene formato ISO."
    if due.tzinfo is None:
        due = due.replace(tzinfo=config.TZ)
    if due <= store.now():
        return "Error: esa fecha ya pasó. Pide una fecha futura."
    with store.connect() as c:
        c.executescript(_SCHEMA)
        rid = c.execute("INSERT INTO reminders (wa_id, text, due_at, created_at) VALUES (?, ?, ?, ?)",
                        (wa_id, texto, _iso(due), _iso(store.now()))).lastrowid
    return f"Recordatorio #{rid} creado para el {_local(_iso(due))}."


def list_pending(wa_id: str) -> str:
    with store.connect() as c:
        c.executescript(_SCHEMA)
        rows = c.execute("SELECT id, text, due_at FROM reminders WHERE wa_id = ? AND status = 'pending' ORDER BY due_at",
                         (wa_id,)).fetchall()
    if not rows:
        return "No hay recordatorios pendientes."
    return "\n".join(f"#{r['id']} · {_local(r['due_at'])} · {r['text']}" for r in rows)


def cancel(wa_id: str, id: int) -> str:
    with store.connect() as c:
        c.executescript(_SCHEMA)
        n = c.execute("UPDATE reminders SET status = 'cancelled' WHERE id = ? AND wa_id = ? AND status = 'pending'",
                      (int(id), wa_id)).rowcount
    return f"Recordatorio #{id} cancelado." if n else f"No encontré un recordatorio pendiente #{id}."


def send_due() -> int:
    """Envía los recordatorios vencidos. Texto libre si hay ventana de 24 h, si no plantilla aprobada."""
    with store.connect() as c:
        c.executescript(_SCHEMA)
        due = c.execute("SELECT id, wa_id, text FROM reminders WHERE status = 'pending' AND due_at <= ?",
                        (_iso(store.now()),)).fetchall()
    for r in due:
        status = "sent"
        try:
            if store.in_window(r["wa_id"]):
                whatsapp.send_text(r["wa_id"], f"⏰ Recordatorio: {r['text']}")
            else:
                whatsapp.send_template(r["wa_id"], config.WHATSAPP_REMINDER_TEMPLATE, config.WHATSAPP_TEMPLATE_LANG, [r["text"]])
            store.record_outbound(r["wa_id"], f"⏰ Recordatorio: {r['text']}")
        except Exception:
            log.exception("No se pudo enviar el recordatorio #%s", r["id"])
            status = "failed"  # no reintentar en bucle: queda visible en el dashboard
        with store.connect() as c:
            c.execute("UPDATE reminders SET status = ?, sent_at = ? WHERE id = ?", (status, _iso(store.now()), r["id"]))
    return len(due)


async def loop(every: int = 30) -> None:
    while True:
        try:
            await asyncio.to_thread(send_due)
        except Exception:
            log.exception("Fallo en el loop de recordatorios")
        await asyncio.sleep(every)


TOOLS = [
    {
        "name": "crear_recordatorio",
        "description": "Programa un recordatorio que se le enviará al usuario por WhatsApp en la fecha y hora indicadas.",
        "parameters": {"type": "object", "properties": {
            "texto": {"type": "string", "description": "Qué hay que recordar, redactado breve."},
            "fecha_hora": {"type": "string", "description": "Fecha y hora local en ISO 8601, ej. 2026-11-26T09:00"},
        }, "required": ["texto", "fecha_hora"]},
    },
    {
        "name": "listar_recordatorios",
        "description": "Lista los recordatorios pendientes del usuario.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "cancelar_recordatorio",
        "description": "Cancela un recordatorio pendiente por su número.",
        "parameters": {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]},
    },
]

HANDLERS = {"crear_recordatorio": create, "listar_recordatorios": list_pending, "cancelar_recordatorio": cancel}
